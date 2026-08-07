var permissionsTitleLabel = chrome.i18n.getMessage("permissionsTitleLabel");
var permissionsAllowText = chrome.i18n.getMessage("permissionsAllowText");
var permissionsDetailText = chrome.i18n.getMessage("permissionsDetailText");
var permissionsSetPerms = chrome.i18n.getMessage("permissionsSetPerms");
var permissionsSetDone = chrome.i18n.getMessage("permissionsSetDone");

document.getElementById("pageTitle2").textContent = permissionsTitleLabel;
document.getElementById("permissionsAllowText").textContent = permissionsAllowText;
document.getElementById("permissionsDetailText").textContent = permissionsDetailText;
document.getElementById("addPermissions").value = permissionsSetPerms;
document.getElementById("addPermissionsRes").textContent = permissionsSetDone;

var permissionsToRequest = {
	origins: [
		"*://*.ica.cz/*",
		"*://*.csob.cz/*",
		"*://*.csob.sk/*",
		"*://*.proebiz.com/*",
		"*://localhost/*"
	]
};

document.querySelector('#addPermissions').addEventListener('click', function(event) {
	browser.permissions.request(permissionsToRequest)
		.then(function(result) {
			if (result === true) {
				document.querySelector('#addPermissionsRes').style.display = 'table-row';
				setTimeout(function() {
					browser.runtime.reload();
					}, 5500);
			}
		});
});