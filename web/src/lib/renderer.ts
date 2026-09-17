/**
 * WebGL2 plumbing for the filter canvas.
 *
 * The renderer owns one program per filter (compiled lazily and cached), the
 * full-screen quad, the camera texture, an optional segmentation-mask texture
 * and — for feedback filters such as *echo trails* — a pair of ping-pong render
 * targets holding the previous composited frame.
 *
 * Coordinate convention: textures are uploaded with `UNPACK_FLIP_Y_WEBGL`, so
 * `v = 0` is the bottom row of the source image and `v = 1` the top. The
 * selfie mirror is applied while *sampling* (`u_flip`), which keeps every
 * screen-space effect aligned with what the user sees.
 */

import { VERTEX_SHADER, getFilter, type FilterDefinition } from "./filters";

export class WebGLUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "WebGLUnavailableError";
  }
}

interface CompiledFilter {
  program: WebGLProgram;
  attribute: number;
  uniforms: Map<string, WebGLUniformLocation | null>;
}

interface RenderTarget {
  texture: WebGLTexture;
  framebuffer: WebGLFramebuffer;
}

export interface RendererOptions {
  /** Called when a shader fails to compile or link. */
  onError?: (message: string) => void;
}

const UNIFORM_NAMES = [
  "u_texture",
  "u_prev",
  "u_mask",
  "u_resolution",
  "u_time",
  "u_flip",
  "u_has_mask",
] as const;

export class FilterRenderer {
  private readonly gl: WebGL2RenderingContext;
  private readonly programs = new Map<string, CompiledFilter>();
  private readonly vao: WebGLVertexArrayObject;
  private readonly quad: WebGLBuffer;
  private readonly videoTexture: WebGLTexture;
  private readonly maskTexture: WebGLTexture;
  private readonly onError: ((message: string) => void) | undefined;

  private current: FilterDefinition;
  private compiled: CompiledFilter;
  private present: CompiledFilter;
  private history: [RenderTarget, RenderTarget] | null = null;
  private historyIndex = 0;
  private maskReady = false;
  private disposed = false;

  constructor(
    private readonly canvas: HTMLCanvasElement,
    options: RendererOptions = {},
  ) {
    const gl = canvas.getContext("webgl2", {
      alpha: false,
      antialias: false,
      depth: false,
      stencil: false,
      premultipliedAlpha: false,
      preserveDrawingBuffer: true,
      powerPreference: "high-performance",
    });
    if (!gl) throw new WebGLUnavailableError("WebGL2 context creation failed");
    this.gl = gl;
    this.onError = options.onError;

    const vao = gl.createVertexArray();
    const quad = gl.createBuffer();
    const videoTexture = gl.createTexture();
    const maskTexture = gl.createTexture();
    if (!vao || !quad || !videoTexture || !maskTexture) {
      throw new WebGLUnavailableError("WebGL2 resource allocation failed");
    }
    this.vao = vao;
    this.quad = quad;
    this.videoTexture = videoTexture;
    this.maskTexture = maskTexture;

    gl.bindVertexArray(vao);
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    gl.bindVertexArray(null);

    this.configureTexture(this.videoTexture, gl.RGBA, gl.RGBA);
    this.configureTexture(this.maskTexture, gl.R8, gl.RED);

    this.current = getFilter(null);
    this.compiled = this.compile(this.current);
    this.present = this.compile(getFilter("original"));
  }

  get filter(): FilterDefinition {
    return this.current;
  }

  get width(): number {
    return this.canvas.width;
  }

  get height(): number {
    return this.canvas.height;
  }

  get hasMask(): boolean {
    return this.maskReady;
  }

  /** Resize the drawing buffer; returns true when the size actually changed. */
  resize(width: number, height: number): boolean {
    const w = Math.max(2, Math.floor(width));
    const h = Math.max(2, Math.floor(height));
    if (this.canvas.width === w && this.canvas.height === h) return false;
    this.canvas.width = w;
    this.canvas.height = h;
    this.releaseHistory();
    return true;
  }

  /** Switch the active filter. Falls back to *original* when it will not build. */
  setFilter(filter: FilterDefinition): boolean {
    if (this.disposed) return false;
    this.current = filter;
    try {
      this.compiled = this.compile(filter);
      this.clearHistory();
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.onError?.(`${filter.id}: ${message}`);
      this.compiled = this.compile(getFilter("original"));
      this.current = getFilter("original");
      this.clearHistory();
      return false;
    }
  }

  /** Upload the current video frame. Returns false when the frame is not ready. */
  uploadVideo(video: HTMLVideoElement): boolean {
    if (this.disposed) return false;
    if (video.readyState < 2 || video.videoWidth === 0 || video.videoHeight === 0) return false;
    const gl = this.gl;
    gl.bindTexture(gl.TEXTURE_2D, this.videoTexture);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    try {
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, video);
    } catch {
      return false;
    } finally {
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    }
    return true;
  }

  /** Upload a single-channel person mask (`0` = background, `255` = person). */
  uploadMask(pixels: Uint8Array, width: number, height: number): void {
    if (this.disposed || width <= 0 || height <= 0) return;
    const gl = this.gl;
    gl.bindTexture(gl.TEXTURE_2D, this.maskTexture);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8, width, height, 0, gl.RED, gl.UNSIGNED_BYTE, pixels);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 4);
    this.maskReady = true;
  }

  clearMask(): void {
    this.maskReady = false;
  }

  /** Draw one frame. `timeSeconds` drives every animated filter. */
  render(timeSeconds: number, mirrored: boolean): void {
    if (this.disposed) return;
    const gl = this.gl;
    const width = this.canvas.width;
    const height = this.canvas.height;
    if (width < 2 || height < 2) return;

    gl.viewport(0, 0, width, height);
    gl.disable(gl.BLEND);
    gl.disable(gl.DEPTH_TEST);

    if (!this.current.needsHistory) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      this.draw(this.compiled, this.current, timeSeconds, mirrored, null);
      gl.bindVertexArray(null);
      return;
    }

    this.ensureHistory(width, height);
    const read = this.target(false);
    const write = this.target(true);
    gl.bindFramebuffer(gl.FRAMEBUFFER, write.framebuffer);
    this.draw(this.compiled, this.current, timeSeconds, mirrored, read.texture);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    // Present the frame we just wrote, then swap the ping-pong pair.
    this.draw(this.present, getFilter("original"), timeSeconds, false, write.texture);
    this.historyIndex = 1 - this.historyIndex;
    gl.bindVertexArray(null);
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    const gl = this.gl;
    for (const { program } of this.programs.values()) gl.deleteProgram(program);
    this.programs.clear();
    this.releaseHistory();
    gl.deleteTexture(this.videoTexture);
    gl.deleteTexture(this.maskTexture);
    gl.deleteBuffer(this.quad);
    gl.deleteVertexArray(this.vao);
  }

  // -- internals ---------------------------------------------------------- //

  private draw(
    compiled: CompiledFilter,
    filter: FilterDefinition,
    timeSeconds: number,
    mirrored: boolean,
    historyTexture: WebGLTexture | null,
  ): void {
    const gl = this.gl;
    const { program, uniforms, attribute } = compiled;

    gl.useProgram(program);
    gl.bindVertexArray(this.vao);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.quad);
    if (attribute >= 0) {
      gl.enableVertexAttribArray(attribute);
      gl.vertexAttribPointer(attribute, 2, gl.FLOAT, false, 0, 0);
    }

    const texture = uniforms.get("u_texture") ?? null;
    if (texture) {
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, this.videoTexture);
      gl.uniform1i(texture, 0);
    }

    const previous = uniforms.get("u_prev") ?? null;
    if (previous) {
      gl.activeTexture(gl.TEXTURE1);
      gl.bindTexture(gl.TEXTURE_2D, historyTexture ?? this.videoTexture);
      gl.uniform1i(previous, 1);
    }

    const mask = uniforms.get("u_mask") ?? null;
    if (mask) {
      gl.activeTexture(gl.TEXTURE2);
      gl.bindTexture(gl.TEXTURE_2D, this.maskTexture);
      gl.uniform1i(mask, 2);
    }

    const resolution = uniforms.get("u_resolution") ?? null;
    if (resolution) gl.uniform2f(resolution, this.canvas.width, this.canvas.height);
    const time = uniforms.get("u_time") ?? null;
    if (time) gl.uniform1f(time, timeSeconds);
    const flip = uniforms.get("u_flip") ?? null;
    if (flip) gl.uniform1f(flip, mirrored ? 1 : 0);
    const hasMask = uniforms.get("u_has_mask") ?? null;
    if (hasMask) gl.uniform1f(hasMask, filter.needsMask && this.maskReady ? 1 : 0);

    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  private compile(filter: FilterDefinition): CompiledFilter {
    const cached = this.programs.get(filter.id);
    if (cached) return cached;
    const gl = this.gl;
    const vertex = this.compileShader(gl.VERTEX_SHADER, VERTEX_SHADER, filter.id);
    const fragment = this.compileShader(gl.FRAGMENT_SHADER, filter.fragment, filter.id);
    const program = gl.createProgram();
    if (!program) throw new Error("could not create program");
    gl.attachShader(program, vertex);
    gl.attachShader(program, fragment);
    // Fixed location, so the single attribute can be resolved once.
    gl.bindAttribLocation(program, 0, "a_position");
    gl.linkProgram(program);
    gl.deleteShader(vertex);
    gl.deleteShader(fragment);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      const log = gl.getProgramInfoLog(program) ?? "unknown link error";
      gl.deleteProgram(program);
      throw new Error(log.trim());
    }
    const uniforms = new Map<string, WebGLUniformLocation | null>();
    for (const name of UNIFORM_NAMES) uniforms.set(name, gl.getUniformLocation(program, name));
    const compiled: CompiledFilter = {
      program,
      attribute: gl.getAttribLocation(program, "a_position"),
      uniforms,
    };
    this.programs.set(filter.id, compiled);
    return compiled;
  }

  private compileShader(type: number, source: string, label: string): WebGLShader {
    const gl = this.gl;
    const shader = gl.createShader(type);
    if (!shader) throw new Error("could not create shader");
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const log = gl.getShaderInfoLog(shader) ?? "unknown compile error";
      gl.deleteShader(shader);
      const kind = type === gl.VERTEX_SHADER ? "vertex" : "fragment";
      throw new Error(`${kind} shader (${label}) failed: ${log.trim()}`);
    }
    return shader;
  }

  private configureTexture(texture: WebGLTexture, internalFormat: number, format: number): void {
    const gl = this.gl;
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    // A 1x1 placeholder keeps the sampler valid before the first real frame.
    gl.texImage2D(
      gl.TEXTURE_2D,
      0,
      internalFormat,
      1,
      1,
      0,
      format,
      gl.UNSIGNED_BYTE,
      new Uint8Array([0, 0, 0, 255]),
    );
  }

  private clearHistory(): void {
    if (!this.history) return;
    const gl = this.gl;
    for (const target of this.history) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, target.framebuffer);
      gl.clearColor(0, 0, 0, 1);
      gl.clear(gl.COLOR_BUFFER_BIT);
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  }

  private releaseHistory(): void {
    if (!this.history) return;
    const gl = this.gl;
    for (const target of this.history) {
      gl.deleteFramebuffer(target.framebuffer);
      gl.deleteTexture(target.texture);
    }
    this.history = null;
    this.historyIndex = 0;
  }

  private ensureHistory(width: number, height: number): void {
    if (this.history) return;
    this.history = [this.createTarget(width, height), this.createTarget(width, height)];
    this.historyIndex = 0;
  }

  private target(write: boolean): RenderTarget {
    if (!this.history) throw new WebGLUnavailableError("history targets are not allocated");
    const index = write ? 1 - this.historyIndex : this.historyIndex;
    return this.history[index];
  }

  private createTarget(width: number, height: number): RenderTarget {
    const gl = this.gl;
    const texture = gl.createTexture();
    const framebuffer = gl.createFramebuffer();
    if (!texture || !framebuffer) throw new WebGLUnavailableError("could not allocate render target");
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture, 0);
    gl.clearColor(0, 0, 0, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    return { texture, framebuffer };
  }
}
