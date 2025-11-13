// madsBridge.js - Bridge client for HTML-to-Python communication
// This file should be included in HTML pages that need to communicate with Python

// Track bridge initialization state
window.bridgeReady = false;
window.bridgeCallbacks = [];

function setupBridge(callback) {
  // Wait for QWebChannel to be available
  if (typeof QWebChannel === 'undefined') {
    console.error("QWebChannel not available. Make sure qwebchannel.js is loaded.");
    return;
  }

  // Store callback if provided
  if (callback) {
    window.bridgeCallbacks.push(callback);
  }

  new QWebChannel(qt.webChannelTransport, function (channel) {
    window.bridge = channel.objects.bridge;
    window.bridgeReady = true;

    // Listen for signals from Python
    window.bridge.messageFromPython.connect(function (msg) {
      console.log("JS received from Python:", msg);
      // Call all registered callbacks
      window.bridgeCallbacks.forEach(function(cb) {
        cb(msg);
      });
    });

    console.log("Bridge initialized successfully");
    
    // Execute any queued bridge operations
    if (window.bridgeQueue) {
      window.bridgeQueue.forEach(function(operation) {
        operation();
      });
      window.bridgeQueue = [];
    }
  });
}

// Utility to send messages to Python
function sendToPython(message) {
  if (window.bridge && window.bridgeReady) {
    window.bridge.receiveMessage(message);
  } else {
    // Queue the message if bridge isn't ready yet
    if (!window.bridgeQueue) {
      window.bridgeQueue = [];
    }
    window.bridgeQueue.push(function() {
      if (window.bridge) {
        window.bridge.receiveMessage(message);
      }
    });
    console.warn("Bridge not ready yet. Message queued. Call setupBridge() first.");
  }
}

// Utility to send structured events to Python (for LSL streaming)
function sendEvent(type, data) {
  // If caller provided a high-level event timestamp (event_timestamp) or a data.timestamp,
  // prefer that value to preserve the action time from the page. Fall back to Date.now().
  const eventData = data || {};
  const preferredTs = (eventData.event_timestamp !== undefined) ? eventData.event_timestamp : (eventData.timestamp !== undefined ? eventData.timestamp : Date.now());

  const event = {
    type: type,
    data: eventData,
    timestamp: preferredTs
  };

  // Remove the transient event_timestamp field to avoid duplication in the payload
  if (event.data.event_timestamp !== undefined) {
    delete event.data.event_timestamp;
  }

  sendToPython(JSON.stringify(event));
}

// Example event types:
// - 'click': Mouse click events
// - 'marker': Custom event markers
// - 'custom': Custom events
// - 'page_load': Page load events
// - 'scroll': Scroll events
// - etc.
