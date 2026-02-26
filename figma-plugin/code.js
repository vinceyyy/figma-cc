"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
figma.showUI(__html__, { width: 560, height: 600 });
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
function sendSelectionInfo() {
    return __awaiter(this, void 0, void 0, function* () {
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
                componentNames: yield extractComponentNames(node),
            };
            figma.ui.postMessage({ type: "selection-info", metadata });
        }
        else {
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
    });
}
function extractTextContent(node) {
    const texts = [];
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
function extractColors(node) {
    const colors = [];
    if ("fills" in node && Array.isArray(node.fills)) {
        for (const fill of node.fills) {
            if (fill.type === "SOLID" && fill.visible !== false) {
                const { r, g, b } = fill.color;
                const hex = `#${toHex(r)}${toHex(g)}${toHex(b)}`;
                if (!colors.includes(hex))
                    colors.push(hex);
            }
        }
    }
    if ("children" in node) {
        for (const child of node.children) {
            for (const c of extractColors(child)) {
                if (!colors.includes(c))
                    colors.push(c);
            }
        }
    }
    return colors;
}
function extractComponentNames(node) {
    return __awaiter(this, void 0, void 0, function* () {
        const names = [];
        if (node.type === "INSTANCE") {
            const comp = yield node.getMainComponentAsync();
            if (comp)
                names.push(comp.name);
        }
        if ("children" in node) {
            for (const child of node.children) {
                names.push(...(yield extractComponentNames(child)));
            }
        }
        return names;
    });
}
function toHex(value) {
    return Math.round(value * 255)
        .toString(16)
        .padStart(2, "0");
}
// Handle messages from UI
figma.ui.onmessage = (msg) => __awaiter(void 0, void 0, void 0, function* () {
    var _a, _b;
    if (msg.type === "resize") {
        figma.ui.resize((_a = msg.width) !== null && _a !== void 0 ? _a : 560, (_b = msg.height) !== null && _b !== void 0 ? _b : 600);
        return;
    }
    if (msg.type === "save-backend-url") {
        figma.clientStorage.setAsync("backendUrl", msg.url);
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
            for (let i = 0; i < sorted.length; i++) {
                const node = sorted[i];
                figma.ui.postMessage({
                    type: "export-progress",
                    current: i + 1,
                    total: sorted.length,
                    frameName: node.name,
                });
                const imageData = yield node.exportAsync({
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
                        componentNames: yield extractComponentNames(node),
                    },
                });
            }
            if (results.length === 1) {
                figma.ui.postMessage({ type: "export-result", image: results[0].image, metadata: results[0].metadata });
            }
            else {
                figma.ui.postMessage({ type: "export-result-multi", frames: results });
            }
        }
        catch (error) {
            figma.ui.postMessage({
                type: "export-error",
                error: String(error),
            });
        }
    }
    if (msg.type === "cancel") {
        figma.closePlugin();
    }
});
