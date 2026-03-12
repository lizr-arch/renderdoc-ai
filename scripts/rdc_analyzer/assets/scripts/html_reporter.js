/**
 * HTML Reporter Scripts
 * =====================
 * 用于 reporters/html_reporter.py 生成的性能分析报告
 * 
 * 提取自: reporters/html_reporter.py._generate_scripts()
 * 提取日期: 2025-07-25
 */

document.addEventListener('DOMContentLoaded', function() {
    const filterBtns = document.querySelectorAll('.filter-btn');
    const rows = document.querySelectorAll('.issues-table tbody tr');
    
    filterBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // Update active state
            filterBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            const filter = this.dataset.filter;
            
            rows.forEach(row => {
                if (filter === 'all') {
                    row.style.display = '';
                } else if (filter.startsWith('category-')) {
                    const category = filter.replace('category-', '');
                    row.style.display = row.dataset.category === category ? '' : 'none';
                } else {
                    row.style.display = row.dataset.severity === filter ? '' : 'none';
                }
            });
        });
    });
});

/**
 * 问题过滤功能
 * @param {string} severity - 严重程度筛选 ('all', 'error', 'warning', 'info')
 */
function filterIssues(severity) {
    // 更新按钮状态
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // 过滤表格行
    document.querySelectorAll('.issues-table tbody tr').forEach(row => {
        if (severity === 'all') {
            row.style.display = '';
        } else {
            const badge = row.querySelector('.severity-badge');
            if (badge && badge.classList.contains(severity)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        }
    });
}