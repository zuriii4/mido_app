(function() {
	var browser = browser || chrome;
	let backgorundPorts = new Map();;
	
	function openBackgroundPort(connectionId) {		
		let backgroundPort = browser.runtime.connect({name: "content->background"});
		backgorundPorts.set(connectionId, backgroundPort);
		
		backgroundPort.onMessage.addListener(function(msg) {
			msg["conn"] = connectionId;
			window.postMessage(msg, "*");
		});
		
		backgroundPort.onDisconnect.addListener(function(p) {
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
			backgorundPorts.delete(data["conn"]);
			window.postMessage({
				"$ditec.dbridge2.Msg" : "closeResp",
				"conn" : data["conn"],
				"error" : errMsg				
			}, "*");
		});
		return backgroundPort;		
	}
	
	window.addEventListener("message", function(event) {
		if (event.source != window) {
			return;
		}		
		let data = event.data; 
		if (data == null || typeof data !== 'object') {
			return;
		}
		
		let msg = data["$ditec.dbridge2.Msg"];
		if (!msg) {
			return;
		} else if ("req" === msg || "openReq" === msg) {				
			let backgroundPort = backgorundPorts.get(data["conn"]);		
			if (!backgroundPort) {
				return;
			}			
			backgroundPort.postMessage(data);
		} else if ("initReq" === msg ) {
			let backgroundPort = openBackgroundPort(data["conn"]);			
			backgroundPort.postMessage(data);
		} else if ("closeReq" === msg ) {
			let backgroundPort = backgorundPorts.get(data["conn"]);
			if (backgroundPort) {
				backgroundPort.disconnect();
				backgorundPorts.delete(data["conn"]);
			}			
			window.postMessage({
				"$ditec.dbridge2.Msg" : "closeResp",
				"conn" : data["conn"],
				"error" : null
			}, "*");
 		} else if ("initResp" === msg ) { 
			if ("fngbdhimbgbonhlibfmiemipheabfdmj" === browser.runtime.id) {
				//som chrome rozsirenie
				if ("japafgjbmccagfkbllkgmnafbcoofccp" === data.extensionId) {
					//zachytil som response z edge rozsirenia -> ukonci spojenie, kedze edge ma prioritu
					let backgroundPort = backgorundPorts.get(data["conn"]);
					if (backgroundPort) {
						backgroundPort.disconnect();
						backgorundPorts.delete(data["conn"]);
					}
				}
			}
		}
		
	}, false);
})();
