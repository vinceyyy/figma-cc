figma.showUI(__html__, { width: 560, height: 600 });

type PluginMessage =
  | { type: "resize"; width?: number; height?: number }
  | { type: "save-backend-url"; url?: string }
  | { type: "export-selection" }
  | { type: "cancel" };

// Send saved backend URL to UI on startup
figma.clientStorage.getAsync("backendUrl").then((url) => {
  if (url) {
    figma.ui.postMessage({ type: "saved-backend-url", url });
  }
});

// Listen for selection changes
figma.on("selectionchange", () => {
  sendSelectionInfo();
});

// Send initial selection info
sendSelectionInfo();

async function sendSelectionInfo() {
  const selection = figma.currentPage.selection;

  if (selection.length === 0) {
    figma.ui.postMessage({ type: "selection-cleared" });
    return;
  }

  if (selection.length === 1) {
    const node = selection[0];
    const metadata = {
      frameName: node.name,
      dimensions: {
        width: Math.round(node.width),
        height: Math.round(node.height),
      },
      textContent: extractTextContent(node),
      colors: extractColors(node),
      componentNames: await extractComponentNames(node),
    };
    figma.ui.postMessage({ type: "selection-info", metadata });
  } else {
    // Multiple frames: sort by x position (left to right)
    const sorted = [...selection].sort((a, b) => a.x - b.x);
    const frames = sorted.map((node) => ({
      frameName: node.name,
      dimensions: {
        width: Math.round(node.width),
        height: Math.round(node.height),
      },
    }));
    figma.ui.postMessage({ type: "multi-selection-info", frames });
  }
}

function extractTextContent(node: SceneNode): string[] {
  const texts: string[] = [];

  if (node.type === "TEXT") {
    texts.push(node.characters);
  }

  if ("children" in node) {
    for (const child of node.children) {
      texts.push(...extractTextContent(child));
    }
  }

  return texts;
}

function extractColors(node: SceneNode): string[] {
  const seen = new Set<string>();

  function walk(n: SceneNode) {
    if ("fills" in n && Array.isArray(n.fills)) {
      for (const fill of n.fills) {
        if (fill.type === "SOLID" && fill.visible !== false) {
          const { r, g, b } = fill.color;
          const hex = `#${toHex(r)}${toHex(g)}${toHex(b)}`;
          seen.add(hex);
        }
      }
    }

    if ("children" in n) {
      for (const child of n.children) {
        walk(child);
      }
    }
  }

  walk(node);
  return [...seen];
}

async function extractComponentNames(node: SceneNode): Promise<string[]> {
  const names: string[] = [];

  if (node.type === "INSTANCE") {
    const comp = await node.getMainComponentAsync();
    if (comp) names.push(comp.name);
  }

  if ("children" in node) {
    for (const child of node.children) {
      names.push(...(await extractComponentNames(child)));
    }
  }

  return names;
}

function toHex(value: number): string {
  return Math.round(value * 255)
    .toString(16)
    .padStart(2, "0");
}

// Handle messages from UI
figma.ui.onmessage = async (msg: PluginMessage) => {
  switch (msg.type) {
    case "resize":
      figma.ui.resize(msg.width ?? 560, msg.height ?? 600);
      return;

    case "save-backend-url":
      figma.clientStorage.setAsync("backendUrl", msg.url);
      return;

    case "export-selection": {
      const selection = figma.currentPage.selection;
      if (selection.length === 0) {
        figma.ui.postMessage({ type: "export-error", error: "No selection" });
        return;
      }

      try {
        // Sort by x position for consistent flow order
        const sorted = [...selection].sort((a, b) => a.x - b.x);
        const results = [];

        for (let i = 0; i < sorted.length; i++) {
          const node = sorted[i];
          figma.ui.postMessage({
            type: "export-progress",
            current: i + 1,
            total: sorted.length,
            frameName: node.name,
          });

          const imageData = await (node as ExportMixin).exportAsync({
            format: "JPG",
            constraint: { type: "SCALE", value: 2 },
          });
          const base64 = figma.base64Encode(imageData);
          results.push({
            image: base64,
            metadata: {
              frameName: node.name,
              dimensions: {
                width: Math.round(node.width),
                height: Math.round(node.height),
              },
              textContent: extractTextContent(node),
              colors: extractColors(node),
              componentNames: await extractComponentNames(node),
            },
          });
        }

        if (results.length === 1) {
          figma.ui.postMessage({ type: "export-result", image: results[0].image, metadata: results[0].metadata });
        } else {
          figma.ui.postMessage({ type: "export-result-multi", frames: results });
        }
      } catch (error) {
        figma.ui.postMessage({
          type: "export-error",
          error: String(error),
        });
      }
      return;
    }

    case "cancel":
      figma.closePlugin();
      return;
  }
};
