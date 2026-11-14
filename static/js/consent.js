(function () {
    "use strict";

    var STORAGE_KEY = "pr_analytics_consent";
    var containerId = window.PR_GTM_CONTAINER_ID || "";
    var banner = null;

    function readChoice() {
        try {
            return window.localStorage.getItem(STORAGE_KEY);
        } catch (error) {
            return null;
        }
    }

    function writeChoice(value) {
        try {
            window.localStorage.setItem(STORAGE_KEY, value);
        } catch (error) {
        }
    }

    function updateConsent(value) {
        if (typeof window.gtag === "function") {
            window.gtag("consent", "update", { analytics_storage: value });
        }
    }

    function clearAnalyticsCookies() {
        var cookies = document.cookie ? document.cookie.split(";") : [];
        cookies.forEach(function (item) {
            var name = item.split("=")[0].trim();
            if (name.indexOf("_ga") !== 0 && name.indexOf("_gid") !== 0) {
                return;
            }
            var expiry = "=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
            document.cookie = name + expiry + "; path=/";
            document.cookie = name + expiry + "; path=/; domain=" + window.location.hostname;
            document.cookie = name + expiry + "; path=/; domain=." + window.location.hostname;
        });
    }

    function loadGtm() {
        if (!containerId || document.getElementById("pr-gtm-script")) {
            return;
        }
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({ "gtm.start": new Date().getTime(), event: "gtm.js" });
        var script = document.createElement("script");
        script.id = "pr-gtm-script";
        script.async = true;
        script.src = "https://www.googletagmanager.com/gtm.js?id=" + encodeURIComponent(containerId);
        document.head.appendChild(script);
    }

    function showBanner() {
        if (!banner) {
            return;
        }
        banner.classList.add("is-visible");
        banner.setAttribute("aria-hidden", "false");
        var acceptButton = document.getElementById("consent-accept");
        if (acceptButton) {
            acceptButton.focus();
        }
    }

    function hideBanner() {
        if (!banner) {
            return;
        }
        banner.classList.remove("is-visible");
        banner.setAttribute("aria-hidden", "true");
    }

    function accept() {
        writeChoice("granted");
        hideBanner();
        updateConsent("granted");
        loadGtm();
    }

    function refuse() {
        var previousChoice = readChoice();
        writeChoice("denied");
        hideBanner();
        clearAnalyticsCookies();
        if (previousChoice === "granted") {
            window.location.reload();
        }
    }

    function manage() {
        showBanner();
    }

    var storedChoice = readChoice();
    if (storedChoice === "granted") {
        updateConsent("granted");
        loadGtm();
    }

    document.addEventListener("DOMContentLoaded", function () {
        banner = document.getElementById("consent-banner");
        if (!banner) {
            return;
        }

        var acceptButton = document.getElementById("consent-accept");
        var refuseButton = document.getElementById("consent-refuse");
        var manageLink = document.getElementById("manage-cookies-link");

        if (acceptButton) {
            acceptButton.addEventListener("click", accept);
        }
        if (refuseButton) {
            refuseButton.addEventListener("click", refuse);
        }
        if (manageLink) {
            manageLink.addEventListener("click", function (event) {
                event.preventDefault();
                manage();
            });
        }
        if (!storedChoice) {
            showBanner();
        }
    });
})();
