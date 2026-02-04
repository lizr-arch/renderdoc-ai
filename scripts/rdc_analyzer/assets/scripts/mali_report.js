        // Analysis data
        const analysisData = $ANALYSIS_DATA;
        
        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab).classList.add('active');
            });
        });
        
        // Function to switch to Textures tab
        // Note: SPIR-V variable names (e.g. Material_Texture2D_0) cannot be directly mapped
        // to RenderDoc ResourceIDs, so we just switch tabs without searching.
        function switchToTexturesTab() {
            // Find and click the Textures tab
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(tab => {
                if (tab.dataset.tab === 'textures') {
                    tab.click();
                    // Clear any existing search filter
                    if (window.textureTable) {
                        window.textureTable.search('').draw();
                    }
                    // Scroll to top of textures section
                    document.getElementById('textures').scrollIntoView({ behavior: 'smooth' });
                }
            });
        }
        
        // Function to format resource detail row - V3 Enhanced with collapsible groups
        function formatResourceDetail(shader) {
            const resources = shader.resources || [];
            if (resources.length === 0) {
                return '<div class="resource-detail-inner"><div class="no-resources">No resources found in SPIR-V metadata</div></div>';
            }
            
            // Group resources by category
            const grouped = {
                'Texture': [],
                'Sampler': [],
                'Buffer': [],
                'Uniform': [],
                'Other': []
            };
            
            resources.forEach(r => {
                const cat = grouped[r.category] ? r.category : 'Other';
                grouped[cat].push(r);
            });
            
            // Category icons (SVG)
            const categoryIcons = {
                'Texture': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>',
                'Sampler': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>',
                'Buffer': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="5" rx="1"/><rect x="2" y="10" width="20" height="5" rx="1"/><rect x="2" y="17" width="20" height="5" rx="1"/></svg>',
                'Uniform': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>',
                'Other': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><circle cx="12" cy="17" r="0.5"/></svg>'
            };
            
            // Category colors
            const categoryColors = {
                'Texture': '#f59e0b',
                'Sampler': '#8b5cf6',
                'Buffer': '#10b981',
                'Uniform': '#3b82f6',
                'Other': '#6b7280'
            };
            
            let html = '<div class="resource-detail-v3">';
            
            // Summary header
            html += `<div class="res-summary-bar">
                <div class="res-summary-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
                        <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
                        <line x1="12" y1="22.08" x2="12" y2="12"/>
                    </svg>
                    Shader Resources
                </div>
                <div class="res-summary-stats">
                    <span class="res-stat" style="--stat-color: #f59e0b;" title="Textures">T:${shader.texture_count || 0}</span>
                    <span class="res-stat" style="--stat-color: #8b5cf6;" title="Samplers">S:${shader.sampler_count || 0}</span>
                    <span class="res-stat" style="--stat-color: #10b981;" title="Buffers">B:${shader.buffer_count || 0}</span>
                    <span class="res-stat" style="--stat-color: #3b82f6;" title="Uniforms">U:${shader.uniform_count || 0}</span>
                </div>
            </div>`;
            
            // Render each category as collapsible group
            const uniqueId = 'res-' + Math.random().toString(36).substr(2, 9);
            
            ['Texture', 'Sampler', 'Buffer', 'Uniform', 'Other'].forEach((category, catIdx) => {
                const items = grouped[category];
                if (items.length === 0) return;
                
                const catLower = category.toLowerCase();
                const groupId = `${uniqueId}-${catLower}`;
                const isExpanded = (category === 'Texture' || category === 'Buffer'); // Default expand Texture and Buffer
                
                html += `<div class="res-group" data-category="${catLower}">
                    <div class="res-group-header ${isExpanded ? 'expanded' : ''}" onclick="toggleResGroup('${groupId}')">
                        <span class="res-group-icon" style="color: ${categoryColors[category]}">
                            ${categoryIcons[category]}
                        </span>
                        <span class="res-group-name">${category}s</span>
                        <span class="res-group-count">${items.length}</span>
                        <span class="res-group-chevron">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="6 9 12 15 18 9"/>
                            </svg>
                        </span>
                    </div>
                    <div class="res-group-content ${isExpanded ? 'expanded' : ''}" id="${groupId}">`;
                
                items.forEach(r => {
                    // Make Texture items clickable
                    const clickable = (category === 'Texture') 
                        ? `onclick="event.stopPropagation(); switchToTexturesTab();" class="res-item clickable" title="View all textures (SPIR-V names may differ from ResourceIDs)"`
                        : `class="res-item"`;
                    
                    html += `<div ${clickable}>
                        <span class="res-item-badge ${catLower}">${category.substring(0, 3)}</span>
                        <span class="res-item-name">${r.name}</span>
                        ${r.set !== undefined ? `<span class="res-item-binding">set=${r.set}, binding=${r.binding}</span>` : ''}
                    </div>`;
                });
                
                html += `</div></div>`;
            });
            
            html += '</div>';
            return html;
        }
        
        // Toggle resource group collapse/expand
        function toggleResGroup(groupId) {
            const content = document.getElementById(groupId);
            const header = content?.previousElementSibling;
            if (content && header) {
                content.classList.toggle('expanded');
                header.classList.toggle('expanded');
            }
        }
        
        function hasDataTables() {
            return window.jQuery && window.jQuery.fn && window.jQuery.fn.DataTable;
        }

        function renderTableFallback(tableId, rows) {
            const table = document.querySelector(tableId);
            if (!table) return;
            let tbody = table.querySelector('tbody');
            if (!tbody) {
                tbody = document.createElement('tbody');
                table.appendChild(tbody);
            }
            tbody.innerHTML = '';
            rows.forEach(row => {
                const tr = document.createElement('tr');
                row.forEach(cell => {
                    const td = document.createElement('td');
                    td.innerHTML = (cell === null || cell === undefined) ? '-' : cell;
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });
        }

        document.addEventListener('DOMContentLoaded', () => {
            const useDataTables = hasDataTables();
            if (useDataTables) {
                window.$ = window.jQuery;
            }
            // Per-file tables with expandable rows
            analysisData.forEach((fileData, fileIdx) => {
                const tableId = `#shader-table-${fileIdx}`;
                const maxCycles = fileData.summary.cycles.max || 1;
                
                const tableData = fileData.shaders.map(shader => {
                    // Stage badge
                    const stage = shader.stage || '??';
                    const stageClass = stage === 'VS' ? 'vs' : 
                                       stage === 'PS' ? 'fs' : 
                                       stage === 'CS' ? 'cs' : 'error';
                    const stageHtml = `<span class="badge badge-${stageClass}">${stage}</span>`;
                    
                    // Hash
                    const hashHtml = `<span class="shader-hash">${shader.hash || '-'}</span>`;
                    
                    // Resource Hint (friendly_label from OpName)
                    const hint = shader.friendly_label || '';
                    const hintHtml = hint 
                        ? `<span class="shader-name" title="${hint}">${hint.substring(0, 25)}${hint.length > 25 ? '...' : ''}</span>`
                        : '<span style="color: var(--text-secondary);">-</span>';
                    
                    // Resource count with breakdown
                    const resCount = shader.resource_count || 0;
                    const resHtml = resCount > 0 
                        ? `<span title="T:${shader.texture_count || 0} S:${shader.sampler_count || 0} B:${shader.buffer_count || 0} U:${shader.uniform_count || 0}">${resCount}</span>`
                        : '<span style="color: var(--text-secondary);">0</span>';
                    
                    if (!shader.valid) {
                        return [
                            '',  // Details control column
                            shader.index,
                            stageHtml,
                            hashHtml,
                            hintHtml,
                            resHtml,
                            shader.size,
                            '-', '-', '-', '-', '-', '-', '-', '-',
                            '<span class="spill-ok">-</span>'
                        ];
                    }
                    
                    const cyclesPct = Math.min(100, (shader.longest_path / maxCycles) * 100);
                    const cycleClass = cyclesPct < 33 ? 'low' : cyclesPct < 66 ? 'medium' : 'high';
                    
                    const cyclesHtml = `<div class="cycles-cell">
                        <span class="cycles-value">${shader.longest_path.toFixed(1)}</span>
                        <div class="cycles-bar"><div class="cycles-fill ${cycleClass}" style="width:${cyclesPct}%"></div></div>
                    </div>`;
                    
                    const spillHtml = shader.has_spilling 
                        ? `<span class="spill-warn">! ${shader.spill_count}</span>`
                        : '<span class="spill-ok">OK</span>';
                    
                    return [
                        '',  // Details control column
                        shader.index,
                        stageHtml,
                        hashHtml,
                        hintHtml,
                        resHtml,
                        shader.size,
                        shader.work_registers,
                        shader.uniform_registers,
                        cyclesHtml,
                        shader.fma_cycles?.toFixed(2) || '-',
                        shader.cvt_cycles?.toFixed(2) || '-',
                        shader.sfu_cycles?.toFixed(2) || '-',
                        shader.load_store_cycles?.toFixed(2) || '-',
                        shader.texture_cycles?.toFixed(2) || '-',
                        spillHtml
                    ];
                });
                
                if (useDataTables) {
                    const table = $(tableId).DataTable({
                        data: tableData,
                        pageLength: 25,
                        order: [[9, 'desc']], // Sort by cycles descending (column index shifted by 2)
                        dom: 'Bfrtip',
                        buttons: ['copy', 'csv', 'excel'],
                        columnDefs: [
                            {
                                className: 'details-control',
                                orderable: false,
                                data: null,
                                defaultContent: '',
                                targets: 0
                            }
                        ],
                        language: {
                            search: "Search:",
                            lengthMenu: "Show _MENU_ shaders",
                            info: "Showing _START_ to _END_ of _TOTAL_ shaders"
                        }
                    });
                    
                    // Add click handler for expandable rows
                    $(tableId + ' tbody').on('click', 'td.details-control', function() {
                        const tr = $(this).closest('tr');
                        const row = table.row(tr);
                        const rowIndex = row.data()[1]; // Index is in column 1 now
                        const shader = fileData.shaders[rowIndex];
                        
                        if (row.child.isShown()) {
                            row.child.hide();
                            tr.removeClass('shown');
                        } else {
                            row.child(formatResourceDetail(shader), 'resource-detail').show();
                            tr.addClass('shown');
                        }
                    });
                } else {
                    renderTableFallback(tableId, tableData);
                }
            });
            
            // Comparison table (if multiple files)
            if (analysisData.length > 1) {
                // Build hash map with shader info (改进版：分离各字段)
                const hashMap = new Map();
                
                analysisData.forEach((fileData, fileIdx) => {
                    fileData.shaders.forEach(shader => {
                        if (shader.valid && shader.hash) {
                            if (!hashMap.has(shader.hash)) {
                                hashMap.set(shader.hash, {
                                    hash: shader.hash,
                                    index: shader.index,
                                    stage: shader.stage || '??',
                                    entry_name: shader.entry_name || 'main',
                                    friendly_label: shader.friendly_label || '',
                                    size: shader.size,
                                    cycles: new Array(analysisData.length).fill(null)
                                });
                            }
                            hashMap.get(shader.hash).cycles[fileIdx] = shader.longest_path;
                        }
                    });
                });
                
                const comparisonData = [];
                hashMap.forEach(item => {
                    // 新的列结构: Index, Stage, Hash, Resource Hint, Size, [Cycles...], Diff
                    const stageClass = item.stage === 'VS' ? 'vs' : 
                                       item.stage === 'PS' ? 'fs' : 
                                       item.stage === 'CS' ? 'cs' : 'error';
                    const stageHtml = `<span class="badge badge-${stageClass}">${item.stage}</span>`;
                    const hashHtml = `<span class="shader-hash">${item.hash}</span>`;
                    const hintHtml = item.friendly_label 
                        ? `<span class="shader-name" title="${item.friendly_label}">${item.friendly_label.substring(0, 25)}${item.friendly_label.length > 25 ? '...' : ''}</span>`
                        : '<span class="text-muted">-</span>';
                    
                    const row = [
                        item.index,
                        stageHtml,
                        hashHtml,
                        hintHtml,
                        item.size
                    ];
                    
                    item.cycles.forEach(c => {
                        row.push(c !== null ? c.toFixed(1) : '-');
                    });
                    
                    // Calculate diff
                    const validCycles = item.cycles.filter(c => c !== null);
                    let diffHtml = '-';
                    if (validCycles.length === analysisData.length) {
                        const diff = item.cycles[1] - item.cycles[0];
                        if (Math.abs(diff) < 0.1) {
                            diffHtml = '<span class="diff-badge diff-same">=</span>';
                        } else if (diff > 0) {
                            diffHtml = `<span class="diff-badge diff-worse">+${diff.toFixed(1)}</span>`;
                        } else {
                            diffHtml = `<span class="diff-badge diff-better">${diff.toFixed(1)}</span>`;
                        }
                    } else if (item.cycles[0] === null) {
                        diffHtml = '<span class="diff-badge diff-new">NEW</span>';
                    } else if (item.cycles[1] === null) {
                        diffHtml = '<span class="diff-badge diff-removed">GONE</span>';
                    }
                    row.push(diffHtml);
                    
                    comparisonData.push(row);
                });
                
                if (useDataTables) {
                    $('#comparison-table').DataTable({
                        data: comparisonData,
                        pageLength: 50,
                        order: [[0, 'asc']], // Sort by index ascending
                        dom: 'Bfrtip',
                        buttons: ['copy', 'csv', 'excel']
                    });
                } else {
                    renderTableFallback('#comparison-table', comparisonData);
                }
            }
            
            // Texture table
            const textureData = [];
            analysisData.forEach((fileData, fileIdx) => {
                const fileName = fileData.summary.file_name.substring(0, 15) + '...';
                const textures = fileData.textures || [];
                
                textures.forEach(tex => {
                    // Image type badge
                    const typeNames = ['1D', '2D', '3D'];
                    const typeName = typeNames[tex.image_type] || '2D';
                    const typeClass = typeName === '2D' ? 'fs' : typeName === '3D' ? 'cs' : 'vs';
                    const typeHtml = `<span class="badge badge-${typeClass}">${typeName}</span>`;
                    
                    // Dimensions
                    let dimStr = `${tex.width}×${tex.height}`;
                    if (tex.depth > 1) {
                        dimStr += `×${tex.depth}`;
                    }
                    
                    // Format - show short name
                    const formatName = tex.format_name.replace('VK_FORMAT_', '');
                    const formatHtml = `<span class="shader-hash" title="${tex.format_name}">${formatName}</span>`;
                    
                    // Usage flags as hex
                    const usageHex = '0x' + tex.usage.toString(16).toUpperCase();
                    
                    // Custom name display
                    const customName = tex.custom_name || '';
                    const customNameHtml = customName 
                        ? `<span class="shader-name" style="color: var(--success);">${customName}</span>`
                        : '<span style="color: var(--text-secondary);">-</span>';
                    
                    textureData.push([
                        fileName,
                        tex.resource_id,
                        customNameHtml,
                        typeHtml,
                        dimStr,
                        formatHtml,
                        tex.mip_levels,
                        tex.array_layers,
                        tex.samples,
                        usageHex
                    ]);
                });
            });
            
            // Store texture table globally for cross-reference function
            if (useDataTables) {
                window.textureTable = $('#texture-table').DataTable({
                    data: textureData,
                    pageLength: 50,
                    order: [[3, 'desc']], // Sort by dimensions descending
                    dom: 'Bfrtip',
                    buttons: ['copy', 'csv', 'excel'],
                    language: {
                        search: "Search:",
                        info: "Showing _START_ to _END_ of _TOTAL_ textures"
                    }
                });
            } else {
                renderTableFallback('#texture-table', textureData);
                window.textureTable = {
                    search: () => ({ draw: () => {} })
                };
            }
            
            // ========================================
            // V3 TEXTURE GRID & LIGHTBOX SYSTEM
            // ========================================
            
            // Build texture list for grid view
            const allTextures = [];
            analysisData.forEach((fileData, fileIdx) => {
                const textures = fileData.textures || [];
                textures.forEach((tex, texIdx) => {
                    const typeNames = ['1D', '2D', '3D'];
                    const typeName = typeNames[tex.image_type] || '2D';
                    let dimStr = `${tex.width}×${tex.height}`;
                    if (tex.depth > 1) dimStr += `×${tex.depth}`;
                    
                    allTextures.push({
                        id: `tex-${fileIdx}-${texIdx}`,
                        fileIdx: fileIdx,
                        fileName: fileData.summary.file_name,
                        resourceId: tex.resource_id,
                        customName: tex.custom_name || '',
                        type: typeName,
                        dims: dimStr,
                        width: tex.width,
                        height: tex.height,
                        depth: tex.depth,
                        format: tex.format_name.replace('VK_FORMAT_', ''),
                        formatFull: tex.format_name,
                        mipLevels: tex.mip_levels,
                        arrayLayers: tex.array_layers,
                        samples: tex.samples,
                        usage: tex.usage,
                        thumbnail: tex.thumbnail || ''  // Base64 Data URI
                    });
                });
            });
            
            // Store globally for lightbox navigation
            window.allTextures = allTextures;
            window.currentLightboxIndex = 0;
            
            // Render texture grid cards
            function renderTextureGrid(textures) {
                const grid = document.getElementById('texture-grid');
                if (!grid) return;
                
                if (textures.length === 0) {
                    const reasons = [];
                    analysisData.forEach(fileData => {
                        const reason = fileData.summary?.texture_data_reason;
                        if (reason) reasons.push(reason);
                    });
                    const reasonHtml = reasons.length
                        ? `<div class="placeholder-hint">${reasons.join('<br>')}</div>`
                        : '';
                    grid.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-muted);">No textures found</div>' + reasonHtml;
                    return;
                }
                
                grid.innerHTML = textures.map((tex, idx) => {
                    // 如果有缩略图则显示图片，否则显示占位符
                    const thumbContent = tex.thumbnail 
                        ? `<img src="${tex.thumbnail}" alt="${tex.customName || 'Texture'}" class="texture-thumb-img" loading="lazy">`
                        : `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                                <circle cx="8.5" cy="8.5" r="1.5"/>
                                <polyline points="21 15 16 10 5 21"/>
                           </svg>`;
                    
                    return `
                    <div class="texture-card ${tex.thumbnail ? 'has-thumb' : ''}" data-index="${allTextures.indexOf(tex)}" onclick="openLightbox(${allTextures.indexOf(tex)})">
                        <div class="texture-card-thumb">
                            ${thumbContent}
                            <span class="type-badge">${tex.type}</span>
                        </div>
                        <div class="texture-card-info">
                            <div class="texture-card-name" title="${tex.customName || 'ResourceID: ' + tex.resourceId}">
                                ${tex.customName || 'Texture #' + tex.resourceId}
                            </div>
                            <div class="texture-card-dims">${tex.dims}</div>
                            <div class="texture-card-format">${tex.format}</div>
                        </div>
                    </div>
                `}).join('');
            }
            
            // Initial render
            renderTextureGrid(allTextures);
            
            // Grid search and filter
            const gridSearch = document.getElementById('texture-grid-search');
            const gridFilter = document.getElementById('texture-grid-filter');
            
            function filterTextures() {
                const searchTerm = (gridSearch?.value || '').toLowerCase();
                const typeFilter = gridFilter?.value || '';
                
                const filtered = allTextures.filter(tex => {
                    const matchSearch = !searchTerm || 
                        tex.customName.toLowerCase().includes(searchTerm) ||
                        tex.resourceId.toString().includes(searchTerm) ||
                        tex.format.toLowerCase().includes(searchTerm);
                    const matchType = !typeFilter || tex.type.includes(typeFilter);
                    return matchSearch && matchType;
                });
                
                renderTextureGrid(filtered);
            }
            
            if (gridSearch) gridSearch.addEventListener('input', filterTextures);
            if (gridFilter) gridFilter.addEventListener('change', filterTextures);
            
            // View toggle (Grid/Table)
            document.querySelectorAll('.view-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const view = btn.dataset.view;
                    
                    // Update button states
                    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    
                    // Toggle views
                    document.querySelectorAll('.texture-view').forEach(v => v.classList.remove('active'));
                    const targetView = document.getElementById(`texture-${view}-view`);
                    if (targetView) targetView.classList.add('active');
                });
            });
        });
        
        // ========================================
        // LIGHTBOX FUNCTIONS (Global scope)
        // ========================================
        
        function openLightbox(index) {
            if (!window.allTextures || index < 0 || index >= window.allTextures.length) return;
            
            window.currentLightboxIndex = index;
            const tex = window.allTextures[index];
            
            // Update lightbox info
            document.getElementById('lightbox-title').textContent = tex.customName || 'Texture #' + tex.resourceId;
            document.getElementById('lightbox-resid').textContent = tex.resourceId;
            document.getElementById('lightbox-dims').textContent = tex.dims;
            document.getElementById('lightbox-format').textContent = tex.format;
            document.getElementById('lightbox-mips').textContent = tex.mipLevels;
            document.getElementById('lightbox-layers').textContent = tex.arrayLayers;
            document.getElementById('lightbox-samples').textContent = tex.samples;
            
            // Update preview image or show placeholder
            const previewImg = document.getElementById('lightbox-preview-img');
            const placeholder = document.getElementById('lightbox-placeholder');
            
            if (tex.thumbnail) {
                // 有缩略图：显示真实图片
                previewImg.src = tex.thumbnail;
                previewImg.style.display = 'block';
                placeholder.style.display = 'none';
            } else {
                // 无缩略图：显示占位符
                previewImg.style.display = 'none';
                placeholder.style.display = 'flex';
            }
            
            // Show lightbox
            document.getElementById('texture-lightbox').classList.add('show');
            document.body.style.overflow = 'hidden';
        }
        
        function closeLightbox() {
            document.getElementById('texture-lightbox').classList.remove('show');
            document.body.style.overflow = '';
        }
        
        function navigateLightbox(direction) {
            if (!window.allTextures) return;
            
            let newIndex = window.currentLightboxIndex + direction;
            if (newIndex < 0) newIndex = window.allTextures.length - 1;
            if (newIndex >= window.allTextures.length) newIndex = 0;
            
            openLightbox(newIndex);
        }
        
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            const lightbox = document.getElementById('texture-lightbox');
            if (!lightbox || !lightbox.classList.contains('show')) return;
            
            if (e.key === 'Escape') closeLightbox();
            if (e.key === 'ArrowLeft') navigateLightbox(-1);
            if (e.key === 'ArrowRight') navigateLightbox(1);
        });
        
        // Close on backdrop click
        document.addEventListener('click', (e) => {
            if (e.target.id === 'texture-lightbox') closeLightbox();
        });
        
        // Channel button toggle (visual only - actual channel filtering requires image data)
        document.querySelectorAll('.channel-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.channel-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });