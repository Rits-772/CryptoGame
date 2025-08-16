// Sidebar JS for CryptoGame
function toggleSidebar() {
    var sidebar = window.parent.document.querySelector('.block-container');
    if (sidebar) {
        sidebar.classList.toggle('sidebar-collapsed');
    }
}
window.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'sidebar_nav') {
        window.parent.postMessage(event.data, '*');
    }
});
