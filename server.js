const http = require("node:http");
const https = require("node:https");
const fs = require("node:fs");
const path = require("node:path");

const root = __dirname;
const publicDir = path.join(root, "public");
const backendOrigin = process.env.BACKEND_ORIGIN || "http://127.0.0.1:8000";

const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
};

function sendFile(res, filePath) {
  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("Not Found");
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, {
      "Content-Type": mimeTypes[ext] || "application/octet-stream",
      "Cache-Control": "no-store",
    });
    res.end(data);
  });
}

function proxyApi(req, res) {
  const target = new URL(req.url || "/", backendOrigin);
  const transport = target.protocol === "https:" ? https : http;
  const proxyReq = transport.request(
    target,
    {
      method: req.method,
      headers: {
        ...req.headers,
        host: target.host,
      },
    },
    (proxyRes) => {
      res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
      proxyRes.pipe(res);
    },
  );

  proxyReq.on("error", () => {
    res.writeHead(502, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ detail: "Backend API is unavailable" }));
  });

  req.pipe(proxyReq);
}

const server = http.createServer((req, res) => {
  const urlPath = decodeURIComponent((req.url || "/").split("?")[0]);
  if (urlPath.startsWith("/api/")) {
    return proxyApi(req, res);
  }

  if (urlPath === "/" || urlPath === "/index.html" || urlPath === "/ad" || urlPath.startsWith("/DmvTqXBpfF.php/")) {
    return sendFile(res, path.join(publicDir, "index.html"));
  }

  const filePath = path.join(publicDir, urlPath);
  if (!filePath.startsWith(publicDir)) {
    res.writeHead(403, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("Forbidden");
    return;
  }

  fs.stat(filePath, (err, stat) => {
    if (!err && stat.isFile()) {
      sendFile(res, filePath);
      return;
    }

    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("Not Found");
  });
});

const port = process.env.PORT || 3000;
server.listen(port, () => {
  console.log(`Admin shell running at http://localhost:${port}`);
  console.log(`Proxying /api requests to ${backendOrigin}`);
});
