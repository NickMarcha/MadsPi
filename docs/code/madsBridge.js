// bridge.js
function setupBridge(callback) {
  new QWebChannel(qt.webChannelTransport, function (channel) {
    window.bridge = channel.objects.bridge;

    // Listen for signals from Python
    bridge.messageFromJs.connect(function (msg) {
      console.log("JS received:", msg);
      if (callback) callback(msg);
    });
  });
}

// Utility to send messages to Python
function sendToPython(message) {
  if (window.bridge) {
    bridge.receiveMessage(message);
  } else {
    console.error("Bridge not ready yet.");
  }
}
