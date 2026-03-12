/**
 * Licht/Donker thema toggle
 * Slaat voorkeur op in localStorage ('menu-maker-theme': 'light' | 'dark')
 */

(function () {
  const STORAGE_KEY = 'menu-maker-theme';

  function getTheme() {
    const opgeslagen = localStorage.getItem(STORAGE_KEY);
    if (opgeslagen) return opgeslagen;
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }

  function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }

  setTheme(getTheme());

  window.toggleTheme = function () {
    const huidig = document.documentElement.getAttribute('data-theme') || 'dark';
    setTheme(huidig === 'dark' ? 'light' : 'dark');
  };

  document.addEventListener('DOMContentLoaded', function () {
    setTheme(getTheme());
  });
})();
