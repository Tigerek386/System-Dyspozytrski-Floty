console.log("Global JS loaded");
// static/js/main.js
const topbar = document.querySelector('.topbar');

window.addEventListener('scroll', () => {
    if (window.scrollY > 10) {
        topbar.classList.add('scrolled');
    } else {
        topbar.classList.remove('scrolled');
    }
});