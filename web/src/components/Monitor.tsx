import type { Dict } from "../lib/i18n";

/**
 * The hero picture: a drawn call tile that does what MirrorLab does, on a loop
 * (see the `.mon-*` keyframes in index.css). Pure SVG, so it costs no request
 * and never touches the camera.
 */

/** MediaPipe's 21 hand landmarks for an open palm, in the SVG's 640×360 space. */
const HAND: ReadonlyArray<readonly [number, number]> = [
  [470, 330], // 0 wrist
  [437, 312], [414, 288], [399, 262], [390, 238], // thumb
  [448, 262], [443, 222], [440, 196], [438, 172], // index
  [472, 254], [473, 208], [474, 180], [475, 154], // middle
  [495, 260], [503, 220], [508, 194], [512, 170], // ring
  [516, 274], [530, 242], [538, 222], [545, 202], // pinky
];

/** Index chains of the five fingers, then the knuckle line across the palm. */
const FINGERS: ReadonlyArray<readonly number[]> = [
  [0, 1, 2, 3, 4],
  [5, 6, 7, 8],
  [9, 10, 11, 12],
  [13, 14, 15, 16],
  [17, 18, 19, 20],
];
const PALM: readonly number[] = [0, 1, 5, 9, 13, 17, 0];

const SKIN = "#d7a98b";

function path(indices: readonly number[]): string {
  return indices
    .map((index, order) => {
      const point = HAND[index];
      return point ? `${order === 0 ? "M" : "L"}${point[0]} ${point[1]}` : "";
    })
    .join(" ");
}

export interface MonitorProps {
  strings: Dict;
}

export function Monitor({ strings }: MonitorProps) {
  const copy = strings.hero.monitor;

  return (
    <figure className="m-0">
      <div className="bezel">
        <div className="glass">
          <svg
            viewBox="0 0 640 360"
            role="img"
            aria-label={copy.label}
            className="block h-auto w-full"
            preserveAspectRatio="xMidYMid slice"
          >
            <defs>
              <filter id="mon-blur" x="-10%" y="-10%" width="120%" height="120%">
                <feGaussianBlur stdDeviation="9" />
              </filter>
              <clipPath id="mon-clip">
                <rect width="640" height="360" />
              </clipPath>
            </defs>

            <g clipPath="url(#mon-clip)">
              <g className="mon-scene">
                {/* The room, blurred: what the other people on the call see behind you. */}
                <g filter="url(#mon-blur)">
                  <rect x="-20" y="-20" width="680" height="400" fill="#2a3138" />
                  <rect x="36" y="34" width="150" height="176" rx="6" fill="#dcc89a" />
                  <rect x="108" y="34" width="6" height="176" fill="#2a3138" opacity="0.5" />
                  <rect x="470" y="28" width="26" height="40" fill="#c9573b" />
                  <rect x="500" y="22" width="22" height="46" fill="#4c7a8c" />
                  <rect x="526" y="32" width="30" height="36" fill="#d8b35a" />
                  <rect x="560" y="26" width="24" height="42" fill="#6b8f5e" />
                  <rect x="452" y="68" width="150" height="10" fill="#4a535a" />
                  <circle cx="568" cy="262" r="46" fill="#f2b66d" opacity="0.85" />
                </g>

                {/* You, in focus. */}
                <path
                  d="M176 372 C184 300 246 276 320 276 C394 276 456 300 464 372 Z"
                  fill="#b9c4c9"
                />
                <rect x="298" y="222" width="44" height="60" rx="14" fill="#c4957a" />
                <ellipse cx="320" cy="172" rx="52" ry="62" fill={SKIN} />
                <path
                  d="M267 166 C262 112 298 94 322 96 C354 96 378 118 373 166 C362 144 342 134 320 134 C298 134 280 146 267 166 Z"
                  fill="#2b2320"
                />
                <circle cx="302" cy="176" r="3.2" fill="#2b2320" />
                <circle cx="338" cy="176" r="3.2" fill="#2b2320" />
                <path d="M306 205 Q320 214 334 205" fill="none" stroke="#8a5a47" strokeWidth="3" strokeLinecap="round" />

                {/* Auto-framing brackets on the face. */}
                <g fill="none" stroke="#ffffff" strokeWidth="3" strokeLinecap="round" opacity="0.9">
                  <path d="M246 130 V104 H272" />
                  <path d="M394 130 V104 H368" />
                  <path d="M246 214 V240 H272" />
                  <path d="M394 214 V240 H368" />
                </g>
              </g>

              {/* The hand, with its landmarks and the hold ring. */}
              <g className="mon-hand">
                <g fill="none" stroke={SKIN} strokeWidth="20" strokeLinecap="round" strokeLinejoin="round">
                  {FINGERS.map((chain) => (
                    <path key={chain.join("-")} d={path(chain)} />
                  ))}
                </g>
                <path d={path(PALM)} fill={SKIN} stroke={SKIN} strokeWidth="26" strokeLinejoin="round" />
                <g fill="none" stroke="#86efc0" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  {FINGERS.map((chain) => (
                    <path key={`l-${chain.join("-")}`} d={path(chain)} />
                  ))}
                  <path d={path(PALM)} />
                </g>
                <g fill="#86efc0">
                  {HAND.map(([x, y], index) => (
                    <circle key={index} cx={x} cy={y} r="3.6" />
                  ))}
                </g>
                <circle cx="472" cy="250" r="88" fill="none" stroke="#ffffff" strokeOpacity="0.25" strokeWidth="4" />
                <circle
                  className="mon-ring"
                  cx="472"
                  cy="250"
                  r="88"
                  fill="none"
                  stroke="#ffffff"
                  strokeWidth="4"
                  strokeLinecap="round"
                />
                <g transform="translate(404 128)">
                  <rect width="116" height="26" rx="13" fill="#0c0e10" opacity="0.82" />
                  <text x="58" y="17.5" textAnchor="middle" fontSize="13" fontWeight="600" fill="#e8ebe6">
                    {copy.hold}
                  </text>
                </g>
              </g>

              {/* The shutter. */}
              <g className="mon-shutter">
                <rect width="640" height="360" fill="#0c0e10" />
                <g transform="translate(320 168)" fill="none" stroke="#e8ebe6" strokeWidth="3" strokeLinecap="round">
                  <rect x="-18" y="-4" width="36" height="28" rx="6" />
                  <path d="M-10 -4 V-14 a10 10 0 0 1 20 0 V-4" />
                </g>
                <text x="320" y="226" textAnchor="middle" fontSize="20" fontWeight="600" fill="#e8ebe6">
                  {copy.covered}
                </text>
              </g>
            </g>
          </svg>

          {/* Status line, like the overlay on a call tile. */}
          <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2 rounded-full bg-black/55 px-3 py-1.5 text-xs font-semibold text-screen-ink backdrop-blur-sm">
            <span className="relative grid h-2.5 w-2.5 place-items-center" aria-hidden="true">
              <span className="mon-live absolute h-2.5 w-2.5 rounded-full bg-tally" />
              <span className="mon-covered absolute h-2.5 w-2.5 rounded-full bg-screen-soft" />
            </span>
            <span className="relative grid">
              <span className="mon-live col-start-1 row-start-1">{copy.live}</span>
              <span className="mon-covered col-start-1 row-start-1">{copy.covered}</span>
            </span>
          </div>
          <ul className="pointer-events-none absolute bottom-3 left-3 flex flex-wrap gap-1.5 text-[11px] font-medium text-screen-ink">
            {[copy.blur, copy.frame, copy.light].map((chip) => (
              <li key={chip} className="rounded-full bg-black/55 px-2.5 py-1 backdrop-blur-sm">
                {chip}
              </li>
            ))}
          </ul>
        </div>

        {/* The device picker of the call app, because that is where it ends up. */}
        <div className="flex items-center gap-2 px-3 pb-1.5 pt-2.5 text-xs text-screen-soft">
          <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <rect x="2.5" y="6" width="14" height="12" rx="3" />
            <path d="m16.5 10 5-3v10l-5-3" />
          </svg>
          <span className="truncate font-medium text-screen-ink">{copy.source}</span>
          <svg viewBox="0 0 24 24" className="ml-auto h-4 w-4 shrink-0 text-signal" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="m5 12.5 4.5 4.5L19 7.5" />
          </svg>
        </div>
      </div>
      <figcaption className="mt-4 text-sm text-ink-soft measure">{strings.hero.caption}</figcaption>
    </figure>
  );
}
