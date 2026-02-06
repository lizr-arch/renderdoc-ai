/**
 * Sample Report Scripts (Mali Shader Analysis)
 * =============================================
 * 用于 generate_sample_report.py 生成的 Mali Shader 分析报告
 * 
 * 提取日期: 2025-07-25
 */

function toggleShader(header) {
    header.parentElement.classList.toggle('expanded');
}

function expandAll() {
    document.querySelectorAll('.shader-item').forEach(el => el.classList.add('expanded'));
}

function collapseAll() {
    document.querySelectorAll('.shader-item').forEach(el => el.classList.remove('expanded'));
}

// Filtering
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('filterType').addEventListener('change', applyFilters);
    document.getElementById('filterBound').addEventListener('change', applyFilters);
    document.getElementById('sortBy').addEventListener('change', applyFilters);
});

function applyFilters() {
    const typeFilter = document.getElementById('filterType').value;
    const boundFilter = document.getElementById('filterBound').value;
    const sortBy = document.getElementById('sortBy').value;
    
    const list = document.getElementById('shaderList');
    const items = Array.from(list.querySelectorAll('.shader-item'));
    
    items.forEach(item => {
        const type = item.dataset.type;
        const bound = item.dataset.bound;
        const showType = typeFilter === 'all' || type === typeFilter;
        const showBound = boundFilter === 'all' || bound === boundFilter;
        item.style.display = (showType && showBound) ? '' : 'none';
    });
    
    // Sort
    items.sort((a, b) => {
        if (sortBy === 'name') return a.querySelector('.name').textContent.localeCompare(b.querySelector('.name').textContent);
        if (sortBy === 'cycles-desc') return parseFloat(b.dataset.cycles) - parseFloat(a.dataset.cycles);
        if (sortBy === 'cycles-asc') return parseFloat(a.dataset.cycles) - parseFloat(b.dataset.cycles);
        return 0;
    });
    items.forEach(item => list.appendChild(item));
}
