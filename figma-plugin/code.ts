figma.showUI(__html__, { width: 560, height: 600 });

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
  const colors: string[] = [];

  if ("fills" in node && Array.isArray(node.fills)) {
    for (const fill of node.fills) {
      if (fill.type === "SOLID" && fill.visible !== false) {
        const { r, g, b } = fill.color;
        const hex = `#${toHex(r)}${toHex(g)}${toHex(b)}`;
        if (!colors.includes(hex)) colors.push(hex);
      }
    }
  }

  if ("children" in node) {
    for (const child of node.children) {
      for (const c of extractColors(child)) {
        if (!colors.includes(c)) colors.push(c);
      }
    }
  }

  return colors;
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
figma.ui.onmessage = async (msg: { type: string; width?: number; height?: number }) => {
  if (msg.type === "resize") {
    figma.ui.resize(msg.width!, msg.height!);
    return;
  }
  if (msg.type === "export-selection") {
    const selection = figma.currentPage.selection;
    if (selection.length === 0) {
      figma.ui.postMessage({ type: "export-error", error: "No selection" });
      return;
    }

    try {
      // Sort by x position for consistent flow order
      const sorted = [...selection].sort((a, b) => a.x - b.x);
      const results = [];

      for (const node of sorted) {
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
  }

  if (msg.type === "cancel") {
    figma.closePlugin();
  }
};
