/*
 * RDC Diff Report Scripts
 * ========================
 * Tab switching and UI interactions
 */

        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tabGroup = btn.closest('.panel');
                const tabId = btn.dataset.tab;
                
                // Update buttons
                tabGroup.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                // Update content
                tabGroup.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tabGroup.querySelector(`#${tabId}`).classList.add('active');
            });
        });
        
        // Evidence anchor click handler
        function jumpToEventId(eventId, markerPath) {
            // Copy to clipboard for easy use in RenderDoc
            const text = `Event ID: ${eventId}\\nMarker: ${markerPath}`;
            navigator.clipboard.writeText(eventId.toString()).then(() => {
                // Show tooltip notification
                const anchor = event.currentTarget;
                const tooltip = document.createElement('div');
                tooltip.textContent = '已复制 Event ID';
                tooltip.style.cssText = `
                    position: fixed;
                    top: ${event.clientY - 40}px;
                    left: ${event.clientX}px;
                    background: var(--accent);
                    color: white;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-size: 12px;
                    z-index: 1000;
                    animation: fadeOut 1.5s forwards;
                `;
                document.body.appendChild(tooltip);
                setTimeout(() => tooltip.remove(), 1500);
            });
        }
        
        // Add fadeOut animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes fadeOut {
                0% { opacity: 1; transform: translateY(0); }
                70% { opacity: 1; transform: translateY(-5px); }
                100% { opacity: 0; transform: translateY(-10px); }
            }
        `;
        document.head.appendChild(style);
