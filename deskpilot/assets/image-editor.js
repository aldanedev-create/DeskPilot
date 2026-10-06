/** Local raster editor. Annotations live on a separate layer until saved. */
export class ImageEditor {
  constructor(canvas, image) {
    this.canvas = canvas;
    this.source = image;
    const scale = Math.min(
      1,
      Math.sqrt(4_000_000 / (image.width * image.height)),
    );
    this.width = Math.round(image.width * scale);
    this.height = Math.round(image.height * scale);
    this.commands = [];
    this.redoCommands = [];
    this.draft = null;
    this.render();
  }

  get dirty() {
    return this.commands.length > 0;
  }

  point(event) {
    const bounds = this.canvas.getBoundingClientRect();
    return {
      x: Math.max(
        0,
        Math.min(
          this.canvas.width,
          ((event.clientX - bounds.left) * this.canvas.width) / bounds.width,
        ),
      ),
      y: Math.max(
        0,
        Math.min(
          this.canvas.height,
          ((event.clientY - bounds.top) * this.canvas.height) / bounds.height,
        ),
      ),
    };
  }

  begin(event, options) {
    if (this.commands.length >= 60)
      throw new Error("Keep edits before adding more (60 edits per session).");
    this.canvas.setPointerCapture(event.pointerId);
    this.draft = { ...options, points: [this.point(event)] };
  }

  move(event) {
    if (!this.draft) return;
    const point = this.point(event);
    if (["pen", "highlighter", "eraser"].includes(this.draft.tool)) {
      if (this.draft.points.length < 1000) this.draft.points.push(point);
    } else {
      this.draft.points[1] = point;
    }
    // Limit live previews to 30 fps; final pointer-up always renders every point.
    if (!this.lastPreview || performance.now() - this.lastPreview >= 32) {
      this.lastPreview = performance.now();
      this.render(this.draft);
    }
  }

  end(event) {
    if (!this.draft) return;
    this.move(event);
    const command = this.draft;
    this.draft = null;
    if (this.canvas.hasPointerCapture(event.pointerId))
      this.canvas.releasePointerCapture(event.pointerId);
    this.commit(command);
  }

  cancel() {
    this.draft = null;
    this.render();
  }

  commit(command) {
    if (this.commands.length >= 60)
      throw new Error("Keep edits before adding more (60 edits per session).");
    if (command.tool === "crop") {
      const a = command.points[0],
        b = command.points[1] || a;
      if (Math.abs(a.x - b.x) < 8 || Math.abs(a.y - b.y) < 8) {
        this.render();
        return;
      }
    }
    this.commands.push(command);
    this.redoCommands = [];
    this.render();
  }

  undo() {
    if (this.commands.length) {
      this.redoCommands.push(this.commands.pop());
      this.render();
    }
  }
  redo() {
    if (this.redoCommands.length) {
      this.commands.push(this.redoCommands.pop());
      this.render();
    }
  }
  reset() {
    this.commands = [];
    this.redoCommands = [];
    this.draft = null;
    this.render();
  }

  makeCanvas(width, height) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    return canvas;
  }

  transform(canvas, command) {
    const contextCanvas = this.makeCanvas(canvas.width, canvas.height);
    let context = contextCanvas.getContext("2d");
    if (command.tool === "rotate") {
      contextCanvas.width = canvas.height;
      contextCanvas.height = canvas.width;
      context = contextCanvas.getContext("2d");
      context.translate(contextCanvas.width, 0);
      context.rotate(Math.PI / 2);
      context.drawImage(canvas, 0, 0);
    } else if (command.tool === "flip") {
      context.translate(canvas.width, 0);
      context.scale(-1, 1);
      context.drawImage(canvas, 0, 0);
    } else if (command.tool === "crop") {
      const a = command.points[0],
        b = command.points[1];
      const x = Math.floor(Math.min(a.x, b.x)),
        y = Math.floor(Math.min(a.y, b.y));
      contextCanvas.width = Math.max(1, Math.floor(Math.abs(a.x - b.x)));
      contextCanvas.height = Math.max(1, Math.floor(Math.abs(a.y - b.y)));
      contextCanvas
        .getContext("2d")
        .drawImage(
          canvas,
          x,
          y,
          contextCanvas.width,
          contextCanvas.height,
          0,
          0,
          contextCanvas.width,
          contextCanvas.height,
        );
    }
    return contextCanvas;
  }

  draw(layer, command) {
    const context = layer.getContext("2d");
    const start = command.points[0],
      end = command.points.at(-1);
    context.save();
    context.strokeStyle = command.color;
    context.fillStyle = command.color;
    context.lineWidth = command.width;
    context.lineCap = "round";
    context.lineJoin = "round";
    const x = Math.min(start.x, end.x),
      y = Math.min(start.y, end.y);
    const w = Math.abs(start.x - end.x),
      h = Math.abs(start.y - end.y);
    if (["pen", "highlighter", "eraser"].includes(command.tool)) {
      if (command.tool === "eraser")
        context.globalCompositeOperation = "destination-out";
      if (command.tool === "highlighter") {
        context.globalAlpha = 0.3;
        context.lineWidth *= 3;
      }
      context.beginPath();
      context.moveTo(start.x, start.y);
      for (const point of command.points.slice(1))
        context.lineTo(point.x, point.y);
      if (command.points.length === 1) {
        context.lineTo(start.x + 0.01, start.y);
      }
      context.stroke();
    } else if (command.tool === "box") context.strokeRect(x, y, w, h);
    else if (command.tool === "redact") {
      context.fillStyle = "#000000";
      context.fillRect(x, y, w, h);
    } else if (command.tool === "ellipse") {
      context.beginPath();
      context.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2);
      context.stroke();
    } else if (command.tool === "text") {
      context.font = command.fontSize + "px Segoe UI, sans-serif";
      context.fillText(command.text || "", start.x, start.y);
    } else if (command.tool === "arrow") {
      const angle = Math.atan2(end.y - start.y, end.x - start.x),
        size = Math.max(12, command.width * 4);
      context.beginPath();
      context.moveTo(start.x, start.y);
      context.lineTo(end.x, end.y);
      context.moveTo(
        end.x - size * Math.cos(angle - 0.5),
        end.y - size * Math.sin(angle - 0.5),
      );
      context.lineTo(end.x, end.y);
      context.lineTo(
        end.x - size * Math.cos(angle + 0.5),
        end.y - size * Math.sin(angle + 0.5),
      );
      context.stroke();
    }
    context.restore();
  }

  render(draft = null) {
    let base = this.makeCanvas(this.width, this.height);
    base.getContext("2d").drawImage(this.source, 0, 0, this.width, this.height);
    let layer = this.makeCanvas(this.width, this.height);
    for (const command of this.commands) {
      if (["crop", "rotate", "flip"].includes(command.tool)) {
        base = this.transform(base, command);
        layer = this.transform(layer, command);
      } else if (command.tool === "adjust") {
        const adjusted = this.makeCanvas(base.width, base.height);
        const context = adjusted.getContext("2d");
        context.filter = `brightness(${command.brightness}%) contrast(${command.contrast}%) saturate(${command.saturation}%)`;
        context.drawImage(base, 0, 0);
        base = adjusted;
      } else this.draw(layer, command);
    }
    if (draft && draft.tool !== "crop") this.draw(layer, draft);
    this.canvas.width = base.width;
    this.canvas.height = base.height;
    const context = this.canvas.getContext("2d");
    context.drawImage(base, 0, 0);
    context.drawImage(layer, 0, 0);
    if (draft?.tool === "crop") {
      const a = draft.points[0],
        b = draft.points.at(-1);
      context.strokeStyle = "#ffffff";
      context.lineWidth = 2;
      context.setLineDash([8, 5]);
      context.strokeRect(a.x, a.y, b.x - a.x, b.y - a.y);
    }
  }
}
