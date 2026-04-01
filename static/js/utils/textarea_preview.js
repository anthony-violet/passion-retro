document.addEventListener('DOMContentLoaded', () => {
    // Find all textareas on the page
    const textareas = document.querySelectorAll('textarea');
    
    textareas.forEach(textarea => {
        // Skip the AI chat input textarea
        if (textarea.id === 'ai-chat-input') return;
        
        // Check if the textarea is already inside a preview container
        if (textarea.closest('.textarea-preview-container')) {
            return;
        }
        
        // Create a container div for the textarea and preview
        const container = document.createElement('div');
        container.className = 'textarea-preview-container';
        
        // Create a preview div
        const preview = document.createElement('div');
        preview.className = 'textarea-preview';
        preview.innerHTML = '<strong>Prévisualisation :</strong>';
        
        // Create a preview content div
        const previewContent = document.createElement('div');
        previewContent.className = 'textarea-preview-content';
        
        // Append the preview content to the preview div
        preview.appendChild(previewContent);
        
        // Insert the container before the textarea in the DOM
        textarea.parentNode.insertBefore(container, textarea);
        
        // Move the textarea into the container
        container.appendChild(textarea);
        
        // Append the preview div to the container
        container.appendChild(preview);
        
        // Function to update the preview
        const updatePreview = () => {
            const content = textarea.value;
            if (content.trim() === '') {
                previewContent.innerHTML = '<em>Aucun contenu à prévisualiser.</em>';
            } else {
                // First, apply BBCode parsing
                let formattedContent = parseBBCode(content);
                // Then, apply Markdown parsing
                formattedContent = parseMarkdown(formattedContent);
                
                previewContent.innerHTML = formattedContent;
            }
        };
        
        // BBCode parser
        function parseBBCode(text) {
            let html = text;
            // Replace BBCode tags with HTML equivalents
            html = html.replace(/\[b\](.*?)\[\/b\]/g, '<strong>$1</strong>');
            html = html.replace(/\[i\](.*?)\[\/i\]/g, '<em>$1</em>');
            html = html.replace(/\[u\](.*?)\[\/u\]/g, '<u>$1</u>');
            html = html.replace(/\[color=([^\]]+)\](.*?)\[\/color\]/g, '<span style="color: $1">$2</span>');
            html = html.replace(/\[citation=(.*?)\](.*?)\[\/citation\]/g, '<blockquote><strong>$1 a écrit :</strong><br>$2</blockquote>');
            return html;
        }
        
        // Markdown parser
        function parseMarkdown(text) {
            let html = text;
            
            // Headers
            html = html.replace(/^#\s+(.*$)/gm, '<h1>$1</h1>');
            html = html.replace(/^##\s+(.*$)/gm, '<h2>$1</h2>');
            html = html.replace(/^###\s+(.*$)/gm, '<h3>$1</h3>');
            
            // Bold and italic (Markdown)
            html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
            html = html.replace(/_(.*?)_/g, '<em>$1</em>');
            html = html.replace(/___(.*?)___/g, '<strong><em>$1</em></strong>');
            
            // Links (Markdown)
            html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2">$1</a>');
            
            // Images (Markdown)
            html = html.replace(/!\[(.*?)\]\((.*?)\)/g, '<img src="$2" alt="$1" style="max-width: 100%;">');
            
            // Blockquotes (Markdown)
            html = html.replace(/^>\s+(.*$)/gm, '<blockquote>$1</blockquote>');
            
            // Horizontal rule (Markdown)
            html = html.replace(/^---$/gm, '<hr>');
            html = html.replace(/^\*\*\*$/gm, '<hr>');
            html = html.replace(/^___$/gm, '<hr>');
            
            // Code blocks (Markdown)
            html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
            html = html.replace(/`(.*?)`/g, '<code>$1</code>');
            
            // Lists (Markdown)
            html = html.replace(/^\*\s+(.*$)/gm, '<li>$1</li>');
            html = html.replace(/^-\s+(.*$)/gm, '<li>$1</li>');
            html = html.replace(/^\d+\.\s+(.*$)/gm, '<li>$1</li>');
            
            // Replace newlines with <br> tags at the end
            html = html.replace(/\n/g, '<br>');
            
            return html;
        }
        
        // Add an event listener to update the preview on input
        textarea.addEventListener('input', updatePreview);
        
        // Initialize the preview
        updatePreview();
    });
});