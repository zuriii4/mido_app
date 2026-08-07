var PORT = 'com.docusign.chrome.sign'
var ok;
if (!ok) {
	ok = true;
	chrome.tabs.onRemoved.addListener(function(tid, removeInfo) {
		App.disconnect(tid);
	})
	chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
		tid = sender.tab.id;
		debug = request.debug
		port = App.get(tid);
		port.postMessage(request);
	});
}
var App = new function() {
	var _ = this;
	_.NMHS = {};
	_.get = function(tid) {
		_NMH = _.NMHS[tid];
		if (!_NMH) {
			_NMH = new NMH(tid);
			_.NMHS[tid] = _NMH
		}
		return _NMH;
	};
	_.remove = function(tid) {
		_.NMHS[tid] = null;
		delete _.NMHS[tid];
	};
	_.disconnect = function(tid) {
		if (_.NMHS[tid]) {
			_.NMHS[tid].disconnect();
		}
	}
	_.disconnectAll = function(){
		for (var key in _.NMHS) {
			_.NMHS[key].disconnect();
		}
	}
};
function NMH(tid) {
	var _ = this;
	_.tid = tid;
	_.onNativeMessage = function(message) {
		chrome.tabs.sendMessage(_.tid, message)
	};
	_.onDisconnected = function() {
		_.shutdown();
	};
	_.disconnect = function() {
		if (_.port) {
			_.port.disconnect();
		}
		_.shutdown();
	};
	_.connect = function() {
		_.port = chrome.runtime.connectNative(PORT);
		_.port.onMessage.addListener(_.onNativeMessage);
		_.port.onDisconnect.addListener(_.onDisconnected);
	};
	_.postMessage = function(message) {
		try {
			if (!_.port) {
				if (!message.cmd) {
					_.onNativeMessage({
						msg : "{\"acao\":\"cancelar\"}"
					})
					_.shutdown();
				} else {
					_.connect();
				}
			}
			if (!!_.port){
				_.port.postMessage(message);	
			}
		} catch (err) {
			_.onNativeMessage({
				msg : "{\"acao\":\"cancelar\", \"error\":\"" + err.message + "\" }"
			})
			console.error(err);
			_.disconnect();
		}
	};
	_.shutdown = function() {
		App.remove(tid);
		_.port = null;
		_.onNativeMessage({
			msg : "{\"acao\":\"cancelar\", \"error\":\"Native Application Shutdown!\" }"
		})
	};
};
