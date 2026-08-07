(function(){
	var DSRequest = 'DocuSignPKI.Request';
	var DSResponse = 'DocuSignPKI.Response';
	var EHLO = 'EHLO';
	var DS_CRID = 'ds-crid';
	var DS_CRID_0 = 'ds-crid-0';
	var existNative=false;
	var countTry=0;
	var receiveMessageFromPage= function (message) {
		sendMessageToExtension(message);
	}
	var sendMessageToExtension= function (message) {
		chrome.runtime.sendMessage(message.detail, receiveMessageFromExtension);
	}
	var receiveMessageFromExtension= function (message) {
		sendMessageToPage(message);
	}
	var sendMessageToPage= function (message) {
		var event = new CustomEvent(DSResponse, {
			detail : JSON.stringify(message)
		});
		document.dispatchEvent(event);
	}
	var serviceCreationDiv= function () {
		var intervalCreate = setInterval(function(){
			createDiv(DS_CRID_0);
			if(existNative){
				createDiv(DS_CRID);
			}else{
				countTry++;
				if(countTry<6000){
					addExtensionId();
				}else{
					clearInterval(intervalCreate);
				}
			}
		},100);
	}
	var addExtensionId= function () {
		var _div_ = document.getElementById(DS_CRID);
		if (_div_ == null) {
			sendMessageToExtension({
				detail : {
					'cmd' : EHLO,
					'msg' : {}
				}
			});
		}
	}
	var createDiv= function (divId) {
		var _div_ = document.getElementById(divId)
		if (_div_ == null) {
			var div = document.createElement('div');
			div.id = divId;
			div.setAttribute(divId, chrome.runtime.id);
			document.body.appendChild(div);
		}
	}
	var idValid=function(){
		return document.getElementById(DS_CRID_NONE)===null;
	}
	var init= function(){
		document.addEventListener(DSRequest, function(event) {
			receiveMessageFromPage(event);
		});
		chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
			if (!!request.cmd && request.cmd ===  EHLO) {
				existNative=true;
				createDiv(DS_CRID);
			} else {
				receiveMessageFromExtension(request);
			}
		});
		serviceCreationDiv();
	}
	init();
})();
