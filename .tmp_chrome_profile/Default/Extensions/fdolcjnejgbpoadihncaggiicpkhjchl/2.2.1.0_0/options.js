
var savedLabel, restoredLabel;
var DEFAULT_LOGGING = false;
var DEFAULT_CLOSE_PAGE_TIMEOUT = 5;
var DEFAULT_INACTIVE_PAGE_TIMEOUT = 600;

function LocalizeStrings() {
    var pageTitelLabel = chrome.i18n.getMessage("appName");
    var loggingEnabledLabel = chrome.i18n.getMessage("optionsLoggingEnabledLabel");
    var pageClosedTimeoutLabel = chrome.i18n.getMessage("optionsPageClosedTimeoutLabel");
    var inactivePageTimeoutLabel = chrome.i18n.getMessage("optionsInactivePageTimeoutLabel");
    savedLabel = chrome.i18n.getMessage("optionsSavedLabel");
    restoredLabel = chrome.i18n.getMessage("optionsRestoredLabel");
    var saveLabel = chrome.i18n.getMessage("optionsSaveLabel");
    var restoreLabel = chrome.i18n.getMessage("optionsRestoreLabel");
    var titleLabel = chrome.i18n.getMessage("optionsTitleLabel");


    document.getElementById("titleLabel").textContent = titleLabel;
    document.getElementById("pageTitle").textContent = pageTitelLabel;
    document.getElementById("pageTitle2").textContent = titleLabel;
    document.getElementById("save").textContent = saveLabel;
    document.getElementById("restore_default").textContent = restoreLabel;
    document.getElementById("inactivePageTimeoutLabel").textContent = inactivePageTimeoutLabel;
    document.getElementById("pageClosedTimeoutLabel").textContent = pageClosedTimeoutLabel;
    document.getElementById("loggingEnabledLabel").textContent = loggingEnabledLabel;
}

function save_options() {

    var loggingEnabled = document.getElementById('loggingEnabled').checked;
    var pageClosedTimeout = document.getElementById('pageClosedTimeout').value;
    var inactivePageTimeout = document.getElementById('inactivePageTimeout').value;

    chrome.storage.local.set({
        loggingEnabled: loggingEnabled,
        pageClosedTimeout: pageClosedTimeout,
        inactivePageTimeout: inactivePageTimeout
    }, function() {

        var status = document.getElementById('status');
        status.textContent = savedLabel;
        setTimeout(function() {
            status.textContent = '';
        }, 750);
    });
}

function restore_default_options() {
    chrome.storage.local.set({
        loggingEnabled: DEFAULT_LOGGING,
        pageClosedTimeout: DEFAULT_CLOSE_PAGE_TIMEOUT,
        inactivePageTimeout: DEFAULT_INACTIVE_PAGE_TIMEOUT
    }, function() {

        document.getElementById('loggingEnabled').checked = DEFAULT_LOGGING;
        document.getElementById('pageClosedTimeout').value = DEFAULT_CLOSE_PAGE_TIMEOUT;
        document.getElementById('inactivePageTimeout').value = DEFAULT_INACTIVE_PAGE_TIMEOUT;

        var status = document.getElementById('status');
        status.textContent = restoredLabel;
        setTimeout(function() {
            status.textContent = '';
        }, 750);
    });
}

function restore_options() {

    LocalizeStrings();

    chrome.storage.local.get({
        loggingEnabled: DEFAULT_LOGGING,
        pageClosedTimeout: DEFAULT_CLOSE_PAGE_TIMEOUT,
        inactivePageTimeout: DEFAULT_INACTIVE_PAGE_TIMEOUT
    }, function(items) {

        document.getElementById('loggingEnabled').checked = items.loggingEnabled;
        document.getElementById('pageClosedTimeout').value = items.pageClosedTimeout;
        document.getElementById('inactivePageTimeout').value = items.inactivePageTimeout;
    });
}
document.addEventListener('DOMContentLoaded', restore_options);
document.getElementById('save').addEventListener('click', save_options);
document.getElementById('restore_default').addEventListener('click', restore_default_options);
