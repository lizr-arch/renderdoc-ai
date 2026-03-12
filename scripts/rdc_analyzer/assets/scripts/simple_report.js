/**
 * Simple Report Scripts
 * =====================
 * 用于 generate_simple_report.py 生成的纹理分析报告
 * 
 * 提取日期: 2025-07-25
 */

/**
 * 纹理搜索过滤功能
 */
function filterTextures() {
    const query = document.getElementById('searchInput').value.toLowerCase();
    const items = document.querySelectorAll('.tex-item');
    let visible = 0;
    
    items.forEach(item => {
        const text = item.textContent.toLowerCase();
        if (text.includes(query)) {
            item.style.display = 'grid';
            visible++;
        } else {
            item.style.display = 'none';
        }
    });
    
    document.getElementById('countDisplay').textContent = `显示 ${visible} 个纹理`;
}
