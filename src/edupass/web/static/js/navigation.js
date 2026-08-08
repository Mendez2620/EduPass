"use strict";

(() => {
  const button = document.querySelector("[data-nav-toggle]");
  const navigation = document.querySelector("[data-role-navigation]");
  if (!button || !navigation) return;
  button.addEventListener("click", () => {
    const expanded = button.getAttribute("aria-expanded") === "true";
    button.setAttribute("aria-expanded", String(!expanded));
    navigation.classList.toggle("site-nav-open", !expanded);
  });
  navigation.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      button.setAttribute("aria-expanded", "false");
      navigation.classList.remove("site-nav-open");
      button.focus();
    }
  });
})();
