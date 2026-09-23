/**
 * CommandPalette 组件测试
 * Cmd+K 弹出,fuzzy search
 */
import React from "react";
import { render, screen, act } from "@testing-library/react";
import { CommandPalette } from "../command-palette";
import { useAppStore } from "@/lib/store";

beforeEach(() => {
  useAppStore.setState({ commandPaletteOpen: false });
});

describe("CommandPalette", () => {
  it("renders closed by default", () => {
    render(<CommandPalette />);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("opens when store state is true", async () => {
    render(<CommandPalette />);
    await act(async () => {
      useAppStore.getState().setCommandPaletteOpen(true);
    });
    expect(screen.queryByRole("textbox")).toBeInTheDocument();
  });

  it("closes on store state false", async () => {
    render(<CommandPalette />);
    await act(async () => {
      useAppStore.getState().setCommandPaletteOpen(true);
    });
    expect(screen.queryByRole("textbox")).toBeInTheDocument();
    await act(async () => {
      useAppStore.getState().setCommandPaletteOpen(false);
    });
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("toggle via store state flip", async () => {
    render(<CommandPalette />);
    expect(useAppStore.getState().commandPaletteOpen).toBe(false);

    await act(async () => {
      const current = useAppStore.getState().commandPaletteOpen;
      useAppStore.getState().setCommandPaletteOpen(!current);
    });
    expect(useAppStore.getState().commandPaletteOpen).toBe(true);
    expect(screen.queryByRole("textbox")).toBeInTheDocument();
  });
});
