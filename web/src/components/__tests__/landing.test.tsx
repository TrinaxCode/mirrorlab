/**
 * Landing-page component tests: bilingual rendering and filter selection.
 * No camera, no MediaPipe, no network — pure DOM.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FilterBar, FilterGallery } from "../FilterBar";
import { GestureGuide } from "../GestureGuide";
import { ShortcutsTable } from "../ShortcutsTable";
import { STRINGS } from "../../lib/i18n";

const es = STRINGS.es;
const en = STRINGS.en;

describe("FilterBar", () => {
  it("lists every filter and reports the selected one", async () => {
    const onSelect = vi.fn();
    render(
      <FilterBar strings={es} lang="es" activeId="sepia" onSelect={onSelect} onStep={() => {}} />,
    );

    const list = screen.getByRole("listbox", { name: es.hud.filter });
    const options = within(list).getAllByRole("option");
    expect(options.length).toBeGreaterThanOrEqual(20);
    expect(within(list).getByRole("option", { name: /Sepia/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    await userEvent.click(within(list).getByRole("option", { name: /Caleidoscopio/ }));
    expect(onSelect).toHaveBeenCalledWith("kaleidoscope");
  });

  it("steps forward and back through the registry", async () => {
    const onStep = vi.fn();
    render(<FilterBar strings={en} lang="en" activeId="original" onSelect={() => {}} onStep={onStep} />);

    await userEvent.click(screen.getByRole("button", { name: en.controls.next }));
    expect(onStep).toHaveBeenCalledWith(1);
    await userEvent.click(screen.getByRole("button", { name: en.controls.previous }));
    expect(onStep).toHaveBeenCalledWith(-1);
  });
});

describe("FilterGallery", () => {
  it("marks the active filter and translates labels", () => {
    render(<FilterGallery strings={en} lang="en" activeId="glitch" onSelect={() => {}} />);
    expect(screen.getByText(en.gallery.applied)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Glitch/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /Night vision/ })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });
});

describe("GestureGuide", () => {
  it("renders both languages from the same registry", () => {
    const { unmount } = render(<GestureGuide strings={es} lang="es" />);
    expect(screen.getByRole("heading", { name: es.gestureGuide.title })).toBeInTheDocument();
    expect(screen.getByText("Palma abierta")).toBeInTheDocument();
    expect(screen.getByText("Pulgar arriba")).toBeInTheDocument();
    unmount();

    render(<GestureGuide strings={en} lang="en" />);
    expect(screen.getByText("Open palm")).toBeInTheDocument();
    expect(screen.getByText("Thumbs up")).toBeInTheDocument();
  });

  it("documents the hands-free actions", () => {
    render(<GestureGuide strings={en} lang="en" />);
    // "Next filter" is bound to both the peace sign and a right swipe, and
    // "Saves a PNG snapshot" to both thumbs up and a swipe up.
    expect(screen.getAllByText("Next filter").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Saves a PNG snapshot").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Freezes / resumes the frame")).toBeInTheDocument();
    expect(screen.getByText(en.gestureGuide.note)).toBeInTheDocument();
  });
});

describe("ShortcutsTable", () => {
  it("lists every shortcut in the active language", () => {
    render(<ShortcutsTable strings={es} />);
    expect(screen.getByText("Guardar una captura PNG")).toBeInTheDocument();
    expect(screen.getByText("Congelar o reanudar la imagen")).toBeInTheDocument();
  });
});
