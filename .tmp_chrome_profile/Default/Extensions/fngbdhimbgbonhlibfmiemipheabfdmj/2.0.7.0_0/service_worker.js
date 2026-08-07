(function() {
	var browser = browser || chrome;
		
	function onContentConnected(contentPort) {
		try {
			var nativePort = null;
			
			contentPort.onMessage.addListener(function(msg) {
				if ("req" === msg["$ditec.dbridge2.Msg"]) {
					try {
						if (msg["op"] === -6) {
							var origin = null;							
							try {
								if (contentPort.sender.url) {
									origin = new URL(contentPort.sender.url).origin; 
								}
							} catch (error) {
								//ignoruj
							}
							
							try {
								if (!origin && contentPort.sender.origin) {
									origin = contentPort.sender.origin; 
								}
							} catch (error) {
							}
							
							if (!origin) {
								origin = null;
							}							
							msg["value"] = origin;
						}
						nativePort.postMessage(msg);
					} catch (e) {
						console.error(e);
						contentPort.postMessage({
							"$ditec.dbridge2.Msg" : "error",
							"error" : e.toString()
						});
					}					
				} else if ("openReq" === msg["$ditec.dbridge2.Msg"]) {					
					try {
						nativePort = browser.runtime.connectNative('sk.ditec.dbridge2.nm');
	
						nativePort.onMessage.addListener(function(msg) {
							msg["$ditec.dbridge2.Msg"] = "resp";
							contentPort.postMessage(msg);
						});
				
						nativePort.onDisconnect.addListener(function(p) {
							var errMsg = null;
							if (chrome.runtime.lastError) {
								//kontorla v chrome
								//napr. Specified native messaging host not found.
								errMsg = chrome.runtime.lastError.message;
							} else if (p.error) {
								//kontorla vo firefoxe
								//napr. No such native application sk.ditec.dbridge2.nm
								errMsg = p.error.message;
							}
							console.error("D.Bridge 2 host disconnected: " + errMsg);
							contentPort.postMessage({
								"$ditec.dbridge2.Msg" : "closeResp",
								"error" : errMsg
							});
						});
						
						contentPort.postMessage({
							"$ditec.dbridge2.Msg" : "openResp"							
						});
					} catch (e) {
						console.error(e);
						contentPort.postMessage({
							"$ditec.dbridge2.Msg" : "error",
							"error" : e.toString()
						});
					}
				}				
			});
	
			contentPort.onDisconnect.addListener(function() {
				if (nativePort!=null) {
					nativePort.disconnect();
				}
			});	

			contentPort.postMessage({
				"$ditec.dbridge2.Msg" : "initResp",
				"version" : browser.runtime.getManifest().version,
				"extensionId" : browser.runtime.id
			});			
		} catch (e) {
			console.error(e);
			contentPort.postMessage({
				"$ditec.dbridge2.Msg": "error",
				"error" : e.toString()
			});
		}
	}
	browser.runtime.onConnect.addListener(onContentConnected);
})();