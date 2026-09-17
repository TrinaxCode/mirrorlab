import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Vitest runs with `globals: true`, but being explicit keeps the DOM tidy even
// when a test renders several components.
afterEach(() => {
  cleanup();
});
