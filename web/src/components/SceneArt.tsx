/**
 * The drawn call picture used as feature art: the same room and person as the hero,
 * parameterised so each feature can show its own before and after. Pure SVG, no
 * requests, and never the camera.
 */

export interface SceneProps {
  /** Unique per instance: SVG filter ids are global to the document. */
  id: string;
  /** Gaussian blur on the room behind the person, in SVG units. */
  blur?: number;
}

function Room() {
  return (
    <>
      <rect x="-20" y="-20" width="680" height="400" fill="#2a3138" />
      <rect x="36" y="34" width="150" height="176" rx="6" fill="#dcc89a" />
      <rect x="108" y="34" width="6" height="176" fill="#2a3138" opacity="0.5" />
      <rect x="470" y="28" width="26" height="40" fill="#c9573b" />
      <rect x="500" y="22" width="22" height="46" fill="#4c7a8c" />
      <rect x="526" y="32" width="30" height="36" fill="#d8b35a" />
      <rect x="560" y="26" width="24" height="42" fill="#6b8f5e" />
      <rect x="452" y="68" width="150" height="10" fill="#4a535a" />
      <circle cx="568" cy="262" r="46" fill="#f2b66d" opacity="0.85" />
    </>
  );
}

function Person() {
  return (
    <>
      <path d="M176 372 C184 300 246 276 320 276 C394 276 456 300 464 372 Z" fill="#b9c4c9" />
      <rect x="298" y="222" width="44" height="60" rx="14" fill="#c4957a" />
      <ellipse cx="320" cy="172" rx="52" ry="62" fill="#d7a98b" />
      <path
        d="M267 166 C262 112 298 94 322 96 C354 96 378 118 373 166 C362 144 342 134 320 134 C298 134 280 146 267 166 Z"
        fill="#2b2320"
      />
      <circle cx="302" cy="176" r="3.2" fill="#2b2320" />
      <circle cx="338" cy="176" r="3.2" fill="#2b2320" />
      <path d="M306 205 Q320 214 334 205" fill="none" stroke="#8a5a47" strokeWidth="3" strokeLinecap="round" />
    </>
  );
}

export function Scene({ id, blur = 0 }: SceneProps) {
  const filterId = `${id}-blur`;
  return (
    <>
      {blur > 0 ? (
        <defs>
          <filter id={filterId} x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation={blur} />
          </filter>
        </defs>
      ) : null}
      <g filter={blur > 0 ? `url(#${filterId})` : undefined}>
        <Room />
      </g>
      <Person />
    </>
  );
}

const FRAME_CLASS = "block h-full w-full";

/** Left half sharp, right half blurred, split by a line you can see. */
export function BackgroundArt() {
  return (
    <svg viewBox="0 0 640 360" aria-hidden="true" className={FRAME_CLASS} preserveAspectRatio="xMidYMid slice">
      <defs>
        <clipPath id="bg-left">
          <rect width="320" height="360" />
        </clipPath>
        <clipPath id="bg-right">
          <rect x="320" width="320" height="360" />
        </clipPath>
      </defs>
      <g clipPath="url(#bg-left)">
        <Scene id="bgl" />
      </g>
      <g clipPath="url(#bg-right)">
        <Scene id="bgr" blur={10} />
      </g>
      <path d="M320 0 V360" stroke="#fff" strokeWidth="2" strokeDasharray="6 6" opacity="0.7" />
    </svg>
  );
}

/** A slow push in on the face, the way the framing eases toward you. */
export function FramingArt() {
  return (
    <svg viewBox="0 0 640 360" aria-hidden="true" className={FRAME_CLASS} preserveAspectRatio="xMidYMid slice">
      <g className="art-zoom">
        <Scene id="fr" blur={6} />
      </g>
      <g fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" opacity="0.9">
        <path d="M246 130 V104 H272" />
        <path d="M394 130 V104 H368" />
        <path d="M246 214 V240 H272" />
        <path d="M394 214 V240 H368" />
      </g>
    </svg>
  );
}

/** Underexposed against a bright window on the left, metered on the face on the right. */
export function LightArt() {
  return (
    <svg viewBox="0 0 640 360" aria-hidden="true" className={FRAME_CLASS} preserveAspectRatio="xMidYMid slice">
      <defs>
        <clipPath id="lt-left">
          <rect width="320" height="360" />
        </clipPath>
        <clipPath id="lt-right">
          <rect x="320" width="320" height="360" />
        </clipPath>
      </defs>
      <g clipPath="url(#lt-left)" style={{ filter: "brightness(0.45) contrast(1.1)" }}>
        <Scene id="ltl" blur={6} />
        <rect x="40" y="30" width="146" height="170" rx="6" fill="#fff" opacity="0.85" />
      </g>
      <g clipPath="url(#lt-right)" style={{ filter: "brightness(1.08)" }}>
        <Scene id="ltr" blur={6} />
      </g>
      <path d="M320 0 V360" stroke="#fff" strokeWidth="2" strokeDasharray="6 6" opacity="0.7" />
    </svg>
  );
}

/** The shutter closed. */
export function ShutterArt() {
  return (
    <svg viewBox="0 0 640 360" aria-hidden="true" className={FRAME_CLASS} preserveAspectRatio="xMidYMid slice">
      <rect width="640" height="360" fill="#0c0e10" />
      <g transform="translate(320 176) scale(2.2)" fill="none" stroke="#e8ebe6" strokeWidth="3" strokeLinecap="round">
        <rect x="-18" y="-4" width="36" height="28" rx="6" />
        <path d="M-10 -4 V-14 a10 10 0 0 1 20 0 V-4" />
      </g>
    </svg>
  );
}

/** Reactions floating up beside the person. */
export function ReactionsArt() {
  return (
    <svg viewBox="0 0 640 360" aria-hidden="true" className={FRAME_CLASS} preserveAspectRatio="xMidYMid slice">
      <Scene id="rx" blur={6} />
      <text x="470" y="210" fontSize="64" textAnchor="middle">
        ❤️
      </text>
      <text x="530" y="140" fontSize="46" textAnchor="middle" opacity="0.85">
        👍
      </text>
      <text x="436" y="120" fontSize="34" textAnchor="middle" opacity="0.6">
        👌
      </text>
    </svg>
  );
}
