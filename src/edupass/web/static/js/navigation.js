"use strict";

(() => {
  const button = document.querySelector("[data-nav-toggle]");
  const navigation = document.querySelector("[data-role-navigation]");
  if (!button || !navigation) return;

  const closeMenu = ({ restoreFocus = false } = {}) => {
    button.setAttribute("aria-expanded", "false");
    navigation.classList.remove("site-nav-open");
    if (restoreFocus) button.focus();
  };

  button.addEventListener("click", () => {
    const expanded = button.getAttribute("aria-expanded") === "true";
    if (expanded) {
      closeMenu();
    } else {
      button.setAttribute("aria-expanded", "true");
      navigation.classList.add("site-nav-open");
    }
  });

  navigation.addEventListener("click", (event) => {
    if (event.target.closest("a")) closeMenu();
  });

  document.addEventListener("click", (event) => {
    if (!navigation.contains(event.target) && !button.contains(event.target)) {
      closeMenu();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMenu({ restoreFocus: true });
    }
  });
})();
