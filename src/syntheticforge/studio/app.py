"""FastAPI application for SyntheticForge Web Studio."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from syntheticforge.config import ForgeConfig, load_config
from syntheticforge.generator.entity_generator import EntityGenerator
from syntheticforge.graph.schema_graph import SchemaGraph


def create_studio_app(schema_path: str | Path) -> FastAPI:
    """Create and configure the FastAPI Web Studio application for a given schema."""
    config: ForgeConfig = load_config(schema_path)
    graph = SchemaGraph(config)
    generator = EntityGenerator(config, graph=graph)

    app = FastAPI(
        title=f"SyntheticForge Studio — {config.name}",
        description="Interactive visual studio for entity DAG exploration and mock data generation.",
        version="0.1.0",
    )

    @app.get("/api/schema")
    def get_schema() -> dict[str, Any]:
        """Return schema metadata, entities, and topological stages."""
        stages = graph.generation_stages()
        entities_data = {}
        for name, ent in config.entities.items():
            entities_data[name] = {
                "count": ent.count,
                "primary_key": ent.primary_key,
                "depends_on": ent.depends_on,
                "foreign_keys": {
                    k: {
                        "entity": v.entity,
                        "field": v.field,
                        "distribution": v.distribution.value,
                        "self_referential": v.self_referential,
                        "deferred": v.deferred,
                    }
                    for k, v in ent.foreign_keys.items()
                },
                "fields": {k: {"type": v.type.value} for k, v in ent.fields.items()},
                "has_lifecycle": ent.lifecycle is not None,
            }

        return {
            "name": config.name,
            "version": config.version,
            "description": config.description,
            "stages": stages,
            "entities": entities_data,
        }

    @app.get("/api/dag")
    def get_dag() -> dict[str, Any]:
        """Return DAG nodes and edges for graph visualization."""
        nodes = []
        stages = graph.generation_stages()
        stage_map = {}
        for s_idx, stage in enumerate(stages):
            for ent in stage:
                stage_map[ent] = s_idx

        for name, ent in config.entities.items():
            nodes.append(
                {
                    "id": name,
                    "label": name,
                    "stage": stage_map.get(name, 0),
                    "count": ent.count,
                    "has_lifecycle": ent.lifecycle is not None,
                }
            )

        edges = []
        for u, v in graph.dag.edges():
            edges.append({"from": u, "to": v})

        return {"nodes": nodes, "edges": edges}

    @app.get("/api/lifecycle/{entity_name}")
    def get_lifecycle(entity_name: str) -> dict[str, Any]:
        """Return lifecycle Markov state machine details for an entity."""
        ent = config.entities.get(entity_name)
        if not ent:
            raise HTTPException(status_code=404, detail="Entity not found")
        if not ent.lifecycle:
            return {"has_lifecycle": False}

        lc = ent.lifecycle
        transitions = [
            {
                "from": t.from_state,
                "to": t.to_state,
                "probability": t.probability,
                "delay_seconds": t.delay_seconds,
            }
            for t in lc.transitions
        ]
        return {
            "has_lifecycle": True,
            "initial_state": lc.initial_state,
            "states": lc.states,
            "transitions": transitions,
        }

    @app.get("/api/preview/{entity_name}")
    def preview_entity(entity_name: str, count: int = 5) -> list[dict[str, Any]]:
        """Generate a live sample of records for the requested entity."""
        ent = config.entities.get(entity_name)
        if not ent:
            raise HTTPException(status_code=404, detail="Entity not found")

        # Generate batch
        records = generator.generate_entity_batch(entity_name, ent, count=min(count, 50))
        return records

    @app.get("/", response_class=HTMLResponse)
    def studio_ui() -> str:
        """Serve the dark-mode interactive Studio UI."""
        return _STUDIO_HTML_TEMPLATE.replace("{{SCHEMA_NAME}}", config.name)

    return app


_STUDIO_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SyntheticForge Studio — {{SCHEMA_NAME}}</title>
  <style>
    :root {
      --bg: #090d16;
      --card-bg: rgba(18, 26, 43, 0.85);
      --card-border: rgba(66, 153, 225, 0.2);
      --text: #f0f6fc;
      --text-muted: #8b949e;
      --accent-cyan: #38bdf8;
      --accent-blue: #3b82f6;
      --accent-purple: #a855f7;
      --accent-green: #22c55e;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; }
    header { background: rgba(13, 17, 23, 0.95); border-bottom: 1px solid var(--card-border); padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; }
    .brand { font-size: 1.25rem; font-weight: 700; color: var(--accent-cyan); display: flex; align-items: center; gap: 0.5rem; }
    .badge { background: rgba(56, 189, 248, 0.15); color: var(--accent-cyan); padding: 0.25rem 0.6rem; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; }
    main { flex: 1; display: grid; grid-template-columns: 350px 1fr 400px; gap: 1.5rem; padding: 1.5rem; }
    .panel { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 1.25rem; display: flex; flex-direction: column; overflow: hidden; backdrop-filter: blur(8px); }
    .panel-title { font-size: 1rem; font-weight: 600; margin-bottom: 1rem; color: var(--accent-cyan); display: flex; align-items: center; justify-content: space-between; }
    .entity-list { list-style: none; overflow-y: auto; display: flex; flex-direction: column; gap: 0.5rem; }
    .entity-item { padding: 0.75rem 1rem; border-radius: 8px; background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.05); cursor: pointer; transition: all 0.2s; }
    .entity-item:hover, .entity-item.active { background: rgba(56, 189, 248, 0.1); border-color: var(--accent-cyan); }
    .entity-name { font-weight: 600; font-size: 0.95rem; }
    .entity-meta { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem; display: flex; justify-content: space-between; }
    .canvas-container { flex: 1; border-radius: 8px; background: rgba(0, 0, 0, 0.3); position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center; }
    svg { width: 100%; height: 100%; }
    .node-rect { fill: #1e293b; stroke: #38bdf8; stroke-width: 2; rx: 8; cursor: pointer; transition: all 0.2s; }
    .node-rect:hover { fill: #0f172a; stroke: #a855f7; stroke-width: 3; }
    .node-text { fill: #f8fafc; font-size: 14px; font-weight: 600; text-anchor: middle; pointer-events: none; }
    .edge-line { stroke: rgba(148, 163, 184, 0.5); stroke-width: 2; marker-end: url(#arrow); }
    pre { background: rgba(0, 0, 0, 0.5); padding: 1rem; border-radius: 8px; overflow: auto; font-family: "JetBrains Mono", Consolas, monospace; font-size: 0.85rem; color: #a5f3fc; flex: 1; }
    button { background: var(--accent-cyan); color: #000; border: none; padding: 0.5rem 1rem; border-radius: 6px; font-weight: 600; cursor: pointer; transition: opacity 0.2s; }
    button:hover { opacity: 0.9; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span>SyntheticForge</span>
      <span class="badge">Web Studio</span>
    </div>
    <div id="schema-badge" class="badge">{{SCHEMA_NAME}}</div>
  </header>
  <main>
    <section class="panel">
      <div class="panel-title">
        <span>Entities & Stages</span>
      </div>
      <ul id="entity-list" class="entity-list"></ul>
    </section>

    <section class="panel">
      <div class="panel-title">
        <span>Topological Entity DAG</span>
      </div>
      <div class="canvas-container">
        <svg id="dag-svg">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8" />
            </marker>
          </defs>
          <g id="dag-edges"></g>
          <g id="dag-nodes"></g>
        </svg>
      </div>
    </section>

    <section class="panel">
      <div class="panel-title">
        <span id="preview-title">Record Preview</span>
        <button id="generate-btn" onclick="fetchPreview()">Generate 5 Samples</button>
      </div>
      <pre id="preview-box">// Select an entity to generate preview records</pre>
    </section>
  </main>

  <script>
    let currentEntity = null;
    let schemaData = null;

    async function init() {
      const res = await fetch('/api/schema');
      schemaData = await res.json();

      const list = document.getElementById('entity-list');
      list.innerHTML = '';
      
      const entities = Object.keys(schemaData.entities);
      entities.forEach((ent, idx) => {
        const info = schemaData.entities[ent];
        const li = document.createElement('li');
        li.className = 'entity-item' + (idx === 0 ? ' active' : '');
        li.innerHTML = `
          <div class="entity-name">${ent}</div>
          <div class="entity-meta">
            <span>Count: ${info.count.toLocaleString()}</span>
            <span>${info.has_lifecycle ? 'State Machine' : 'Relational'}</span>
          </div>
        `;
        li.onclick = () => selectEntity(ent);
        list.appendChild(li);
      });

      if (entities.length > 0) {
        selectEntity(entities[0]);
      }
      renderDag();
    }

    function selectEntity(name) {
      currentEntity = name;
      document.querySelectorAll('.entity-item').forEach(el => {
        el.classList.toggle('active', el.querySelector('.entity-name').innerText === name);
      });
      document.getElementById('preview-title').innerText = `${name} Preview`;
      fetchPreview();
    }

    async function fetchPreview() {
      if (!currentEntity) return;
      const box = document.getElementById('preview-box');
      box.innerText = '// Synthesizing records...';
      try {
        const res = await fetch(`/api/preview/${currentEntity}?count=5`);
        const data = await res.json();
        box.innerText = JSON.stringify(data, null, 2);
      } catch (err) {
        box.innerText = '// Error fetching records: ' + err;
      }
    }

    async function renderDag() {
      const res = await fetch('/api/dag');
      const data = await res.json();
      const svgNodes = document.getElementById('dag-nodes');
      const svgEdges = document.getElementById('dag-edges');
      svgNodes.innerHTML = '';
      svgEdges.innerHTML = '';

      const nodeCoords = {};
      const stageGroups = {};
      data.nodes.forEach(n => {
        stageGroups[n.stage] = stageGroups[n.stage] || [];
        stageGroups[n.stage].push(n);
      });

      const stages = Object.keys(stageGroups).sort();
      const stageWidth = 500 / Math.max(1, stages.length);

      stages.forEach((st, sIdx) => {
        const group = stageGroups[st];
        const stepY = 350 / (group.length + 1);
        group.forEach((node, nIdx) => {
          const x = 70 + sIdx * 160;
          const y = (nIdx + 1) * stepY;
          nodeCoords[node.id] = { x, y };

          const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
          g.onclick = () => selectEntity(node.id);

          const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
          rect.setAttribute('x', x - 60);
          rect.setAttribute('y', y - 20);
          rect.setAttribute('width', 120);
          rect.setAttribute('height', 40);
          rect.setAttribute('class', 'node-rect');

          const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
          text.setAttribute('x', x);
          text.setAttribute('y', y + 5);
          text.setAttribute('class', 'node-text');
          text.textContent = node.label;

          g.appendChild(rect);
          g.appendChild(text);
          svgNodes.appendChild(g);
        });
      });

      data.edges.forEach(edge => {
        const from = nodeCoords[edge.from];
        const to = nodeCoords[edge.to];
        if (from && to) {
          const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          line.setAttribute('x1', from.x + 60);
          line.setAttribute('y1', from.y);
          line.setAttribute('x2', to.x - 60);
          line.setAttribute('y2', to.y);
          line.setAttribute('class', 'edge-line');
          svgEdges.appendChild(line);
        }
      });
    }

    window.onload = init;
  </script>
</body>
</html>
"""
