/**
 * Landing-page component tests: bilingual rendering and filter selection.
 * No camera, no MediaPipe, no network — pure DOM.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FilterBar, FilterGallery } from "../FilterBar";
import { GestureGuide } from "../GestureGuide";
import { Control } from "../Control";
import { Install } from "../Install";
import { ShortcutsTable } from "../ShortcutsTable";
import { SnapshotTray, type TrayItem } from "../SnapshotTray";
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
    // "Saves a snapshot to the tray" to both thumbs up and a swipe up.
    expect(screen.getAllByText("Next filter").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Saves a snapshot to the tray").length).toBeGreaterThanOrEqual(2);
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

describe("SnapshotTray", () => {
  const item = (id: number): TrayItem => ({
    id,
    url: `blob:test-${id}`,
    blob: new Blob(["x"], { type: "image/png" }),
    filename: `mirrorlab-${id}.png`,
    takenAt: new Date(2026, 0, 1, 12, 0, id),
  });

  it("explains that nothing downloads on its own when it is empty", () => {
    render(<SnapshotTray strings={es} items={[]} onDiscard={() => {}} onClear={() => {}} />);
    expect(screen.getByText(es.tray.empty)).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("offers an explicit download per snapshot and can discard it", async () => {
    const onDiscard = vi.fn();
    render(<SnapshotTray strings={en} items={[item(1), item(2)]} onDiscard={onDiscard} onClear={() => {}} />);

    const links = screen.getAllByRole("link", { name: en.tray.download });
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("download", "mirrorlab-1.png");

    await userEvent.click(screen.getAllByRole("button", { name: en.tray.discard })[0]);
    expect(onDiscard).toHaveBeenCalledWith(1);
  });
});

describe("Control", () => {
  it("lists each gesture with its hold time", () => {
    render(<Control strings={en} />);
    expect(screen.getByText("Open palm")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /How long to hold it: 1\.6 s/ })).toBeInTheDocument();
  });
});

describe("Install", () => {
  it("switches the steps with the operating-system tabs", async () => {
    render(<Install strings={es} />);
    await userEvent.click(screen.getByRole("tab", { name: "Windows" }));
    expect(screen.getByRole("tab", { name: "Windows" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText(/OBS Virtual Camera/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Linux" }));
    expect(screen.getByText(/v4l2loopback devices=1/)).toBeInTheDocument();
  });
});
