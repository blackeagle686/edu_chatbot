(function () {
    const savedTheme = localStorage.getItem('wasla-theme') || 'dark';
    if (savedTheme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
    }
})();
