Log("log", "background.js loaded");

var hostName = "cz.ica.icapkiservice.host";
var nativeport = null;
var pagePortRegister = [];
var messageRegister = [];
var lastMessageSourcePage;
var timeout = null;

var loggingEnabled = false;
var pageClosedTimeout = 10;
var inactivePageTimeout = 600;

var pageClosedTimeoutMin = 2;
var inactivePageTimeoutMin = 60;
var DIR = "directive";
var ERR = "error";
var DIR_TERMINATE = "close";
var DIR_EXTENSION_CONNECTED = "connectExtension";
var DIR_EXTENSION_VERSION = "extensionVersion";
var DIR_EXTENSION_ID = "extensionID";
var PURPOSE_COOKIE = "cookie";

var isFirefox = (navigator.userAgent.toLowerCase().indexOf('firefox') != -1);
/***************** Load Options *******************************/

function LoadOptions() {
    chrome.storage.local.get({
        loggingEnabled: false,
        pageClosedTimeout: 10,
        inactivePageTimeout: 600
    }, function(items) {
        loggingEnabled = items.loggingEnabled;

        pageClosedTimeout = items.pageClosedTimeout;
        if(pageClosedTimeout < pageClosedTimeoutMin)
            pageClosedTimeout = pageClosedTimeoutMin;

        inactivePageTimeout = items.inactivePageTimeout;
        if(inactivePageTimeout < inactivePageTimeoutMin)
            inactivePageTimeout = inactivePageTimeoutMin;
        Log("info", "LoadOptions(): loggingEnabled: " + loggingEnabled + "\npageClosedTimeout: " + pageClosedTimeout + "\ninactivePageTimeout: " + inactivePageTimeout);
    });
}
/***************** Logging ************************************/

function Log(level, message) {
    if(loggingEnabled) {
        switch (level) {
            case "log":
                console.log(message);
                break;
            case "info":
                console.info(message);
                break;
            case "warn":
                console.warn(message);
                break;
            case "error":
                console.error(message);
                break;
            default :
                console.log(message);
                break;
        }
    }
}

/************* Communication functions to page*****************/
//process message from the page
function onMessageFromPage(m, sender) {

    var tabId = 0;
	
	var cbAfterTabId = function(tabId) {
		Log("log", "onMessageFromPage: Received message from: " + tabId + ". Message text: " + JSON.stringify(m));

		//process when directive
		if(m.type == DIR) {
			if(m.content == DIR_EXTENSION_CONNECTED) {
				//send the same response to the page
				sendMessageToPage(Directive(DIR_EXTENSION_CONNECTED), tabId);
			}
			else if(m.content == DIR_EXTENSION_VERSION) {
				sendMessageToPage(GetExtensionVersionMessage(), tabId);
			}
			else if(m.purpose == PURPOSE_COOKIE) {
				messageRegister[m.id] = tabId;
				lastMessageSourcePage = tabId;
				addCookieAndSend(m);
			}
		} else {
			messageRegister[m.id] = tabId;
			lastMessageSourcePage = tabId;
			sendNativeMessage(m);
		}
	};
	
    if(isFirefox) {
        var getCurrentTabId = function(tabs) {
            tabId = tabs[0].id;
			cbAfterTabId(tabId);
        };
        chrome.tabs.query({currentWindow: true, active: true}, getCurrentTabId);
    }
    else {
        tabId = sender.sender.tab.id;
		cbAfterTabId(tabId);
    }
}

function addCookieAndSend(m) {
    Log("log", "addCookieAndSend: start");
    var decodedContent = JSON.parse(decodeFromBase64(m.content));

    var cookieObjects = JSON.parse(decodedContent.function.inParamsVal[0]);
    //ve formátu [{"url": cookieURL, "name": cookieName}, {"url": cookieURL, "name": cookieName}, ...]

    var cookieObjectsNo = cookieObjects.length;
    var cookieIterator = 0;
    var cookieString = "";

    var cookieCb = function(cookie) {
        if(cookie == null) {
            Log("error", "addCookieAndSend: cookie not found.");
            var errorMsgToPage = GetExtensionErrorMessage(11008, "Error retrieving cookie.", "unable to retrieve cookie");
            sendMessageToPage(errorMsgToPage, lastMessageSourcePage);
            return;
        }
        cookieIterator++;
        if(cookieIterator == cookieObjectsNo) {
            cookieString += cookie.name + "=" + cookie.value;
            var newContent = decodedContent;
            newContent.function.inParamsVal[0] = cookieString;
            m.content = encodeToBase64(JSON.stringify(newContent));
            m.type = "call";
            Log("info", "addCookieAndSend: cookie finished. Sending to the host.");
            sendNativeMessage(m);
        }
        else {
            cookieString += cookie.name + "=" + cookie.value + "; ";
        }
    };

    for(var i=0; i< cookieObjectsNo; i++) {
        chrome.cookies.get(cookieObjects[i], cookieCb);
    }
}

function onMessagingFromPageDisconnected(sender) {
    var tabId = sender.sender.tab.id;
    chrome.action.disable(tabId);
    Log("info", "onMessagingFromPageDisconnected: Messaging from page disconnected. Setting 'port = null', closing ICAPKIServiceHost");
    pagePortRegister[tabId] = null;
    delete pagePortRegister[tabId];
    if(Object.keys(pagePortRegister).length == 0) {
        resetTimeout(pageClosedTimeout);
    }
    else {
        Log("log", "resetTimeout: some ports are still active, no reset of timeout.");
    }
}

//send message to the page
function sendMessageToPage(m, tabId) {
    Log("log", "sendMessageToPage: Sending message to the page: " + JSON.stringify(m));
    if(pagePortRegister[tabId] != null)
        pagePortRegister[tabId].postMessage(m);
    else
        Log("error", "Page port is null! Unable to send message to tab with id: " + tabId);
}

function Directive(m) {
    return {type: DIR, content: m};
}

function GetExtensionErrorMessage(num, desc, msg) {
    var errorText = "Extension: Description: " + desc + "   Message: " + msg;
    return {type: ERR, number: num, content: encodeToBase64(errorText)};
}

function GetExtensionVersionMessage() {
    var obj = {};
    obj[DIR_EXTENSION_VERSION] = chrome.runtime.getManifest().version;
    var msg = Directive(obj);
    return msg;
}

function GetExtensionIdMessage() {
    var obj = {};
    obj[DIR_EXTENSION_ID] = chrome.runtime.id;
    var msg = Directive(obj);
    return msg;
}

/************* Native Messaging Communication functions *****************/
function connectNativeHost() {
    Log("log", "connectNativeHost: Trying to connect nativeHost: " + hostName);
    if(nativeport == null) {
        Log("log", "connectNativeHost: Connection 'nativeport == null', establishing connection to the native host");
        nativeport = chrome.runtime.connectNative(hostName);
        if(nativeport == null) {
            Log("error", "connectNativeHost: Unable to establish connection to the native host");
            return false;
        }
        nativeport.onMessage.addListener(onNativeMessage);
        nativeport.onDisconnect.addListener(onNativeMessagingDisconnect);
    }
    else {
        Log("log", "connectNativeHost: Connection 'nativeport != null', connection to the native host already established");
    }
    return true;
}

function onNativeMessagingDisconnect() {
    Log("info", "onNativeMessagingDisconnect: Native messaging disconnected from native host. Setting 'port = null'");
    nativeport = null;
    var portCount = Object.keys(pagePortRegister).length;
    for(var i=0; i<portCount; i++) {
        var tabId = Object.keys(pagePortRegister)[i];
        pagePortRegister[tabId].disconnect();
        pagePortRegister[tabId] = null;
        delete pagePortRegister[tabId];
    }
}

function terminateNativeHost() {
    Log("info", "terminateNativeHost: Sending the close message to the ICAPKIServiceHost");
    sendNativeMessage(Directive(DIR_TERMINATE));
    nativeport.disconnect();
    onNativeMessagingDisconnect();
}

//send native message to the host app
function sendNativeMessage (m) {
    if(m == null) {
        Log("error", "sendNativeMessage: Message to be send is empty!");
        return;
    }
    if(!connectNativeHost()) {
        Log("error", "sendNativeMessage: No connection to the native host");
        return;
    }

    Log("log", "sendNativeMessage: Sending message to the native host: " + JSON.stringify(m));
    nativeport.postMessage(m);

    resetTimeout(inactivePageTimeout);
}

//process message from native messaging
function onNativeMessage(m) {
    Log("log", "onNativeMessage: Received message from the native host: " + JSON.stringify(m));

    if(m.type == DIR && m.content == DIR_EXTENSION_ID) {
        //send response with extension ID to the host
        Log("info", "onNativeMessage: Extension version query detected.");
        sendNativeMessage(GetExtensionIdMessage());
    } else {
        var tabId = messageRegister[m.id];
        if(tabId == undefined || tabId == null)
            tabId = lastMessageSourcePage;
        sendMessageToPage(m, tabId);
    }
}

function resetTimeout(seconds) {
    Log("log", "resetTimeout: Reseting timeout. Automatic termination of the host app in " + seconds + " seconds");
    clearTimeout(timeout);
    timeout = setTimeout(terminateNativeHost, seconds*1000);
}

/************* OnLoad commands *****************/
function connected(portToPage) {
    Log("log", "connected: start");
    var tabId = 0;
	
	var pagePortRegisterAdd = function(tabId) {
		LoadOptions();
		Log("log", "connected: Background page '" + portToPage.sender.url + "' connected to the page through pagePort with tab id:" + tabId);
		pagePortRegister[tabId] = portToPage;
		pagePortRegister[tabId].onMessage.addListener(onMessageFromPage);
		pagePortRegister[tabId].onDisconnect.addListener(onMessagingFromPageDisconnected);
	};
	
    if(isFirefox) {
        var getCurrentTabId = function(tabs) {
            tabId = tabs[0].id;
			chrome.action.enable(tabId);
			pagePortRegisterAdd(tabId);
        };
        chrome.tabs.query({currentWindow: true, active: true}, getCurrentTabId);
    }
    else {
        tabId = portToPage.sender.tab.id;
        chrome.action.enable(tabId);
		pagePortRegisterAdd(tabId);
    }
}

function installed() {
	var permissionsURL = browser.runtime.getURL("permissions.html");
	
	browser.tabs.create({url: permissionsURL});
}

if(isFirefox) {
    chrome.runtime.onConnect.addListener(connected);
	chrome.runtime.onInstalled.addListener(installed);
}
else { //Chrome, Opera
    chrome.runtime.onConnectExternal.addListener(connected);
}

chrome.action.disable();

/************ Utils ***************************/

function decodeFromBase64(encoded) {
    return decodeURIComponent(escape(atob(encoded)));
}

function encodeToBase64(decoded) {
    return btoa(unescape(encodeURIComponent(decoded)));
}