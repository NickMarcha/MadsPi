# MadsBridge Documentation

## Overview

MadsBridge is a communication system that enables seamless two-way communication between JavaScript/HTML frontend and Python backend in the MadsPipeline application. It leverages Qt's QWebChannel technology to provide a robust, type-safe bridge between web content and native Python functionality.

## Architecture

```none
┌─────────────────┐    QWebChannel    ┌─────────────────┐
│   JavaScript    │ ◄──────────────► │     Python      │
│   (Frontend)    │                   │    (Backend)    │
└─────────────────┘                   └─────────────────┘
        │                                        │
        │                                        │
        ▼                                        ▼
┌─────────────────┐                   ┌─────────────────┐
│  madsBridge.js  │                   │  madsBridge.py  │
│  (Client API)   │                   │  (Server API)   │
└─────────────────┘                   └─────────────────┘
```

## Quick Start

### 1. Include Required Scripts

```html
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Your MadsPipeline Page</title>
    <!-- Qt WebChannel support -->
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <!-- MadsBridge client library -->
    <script src="madsBridge.js"></script>
  </head>
  <body>
    <!-- Your content here -->
  </body>
</html>
```

[madsBridge.js](/docs/code/madsBridge.js)

### 2. Initialize the Bridge

```javascript
document.addEventListener("DOMContentLoaded", function () {
  // Setup bridge with message handler
  setupBridge(function (message) {
    console.log("Received from Python:", message);
    // Handle incoming messages from Python
  });
});
```

### 3. Send Messages to Python

```javascript
// Send a simple string message
sendToPython("Hello from JavaScript!");

// Send structured data as JSON string
sendToPython(
  JSON.stringify({
    action: "start_recording",
    parameters: {
      duration: 30,
      quality: "high",
    },
  })
);
```

## Example

[BridgeExample.html](/docs/code/BridgeExample.html)
