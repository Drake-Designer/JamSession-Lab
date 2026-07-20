/**
 * Countdown lock on the "Resend verification email" button.
 * While the server-side cooldown is active the button stays disabled.
 */
(function () {
  function formatLabel(template, seconds) {
    return template.replace("{seconds}", String(seconds));
  }

  function initResendForm(form) {
    var button = form.querySelector("[data-resend-verification-btn]");
    if (!button) {
      return;
    }

    var remaining = parseInt(form.getAttribute("data-cooldown-seconds") || "0", 10);
    if (Number.isNaN(remaining) || remaining < 0) {
      remaining = 0;
    }

    var labelReady =
      button.getAttribute("data-label-ready") || "Resend verification email";
    var labelWait =
      button.getAttribute("data-label-wait") || "Resend available in {seconds}s";
    var timerId = null;

    function setReady() {
      button.disabled = false;
      button.textContent = labelReady;
      button.classList.remove("resend-verification-btn--waiting");
      form.setAttribute("data-cooldown-seconds", "0");
    }

    function tick() {
      if (remaining <= 0) {
        if (timerId !== null) {
          window.clearInterval(timerId);
          timerId = null;
        }
        setReady();
        return;
      }

      button.disabled = true;
      button.classList.add("resend-verification-btn--waiting");
      button.textContent = formatLabel(labelWait, remaining);
      form.setAttribute("data-cooldown-seconds", String(remaining));
      remaining -= 1;
    }

    if (remaining > 0) {
      tick();
      timerId = window.setInterval(tick, 1000);
    } else {
      setReady();
    }
  }

  document
    .querySelectorAll("[data-resend-verification]")
    .forEach(initResendForm);
})();
