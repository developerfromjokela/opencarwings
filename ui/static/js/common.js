function showNotification({ message, title = '', type = 'success', persist_id=undefined}) {
    // Create notification element
    const notification = document.createElement('div');
    // Set styles and icon based on type
    let typeStyles, iconPath, content;
    switch (type) {
        case 'success':
            typeStyles = 'bg-green-100 text-green-800';
            iconPath = '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />';
            content = `<span>${message}</span>`;
            break;
        case 'error':
            typeStyles = 'bg-red-100 text-red-800';
            iconPath = '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />';
            content = `<span>${message}</span>`;
            break;
        case 'info':
            typeStyles = 'bg-blue-100 text-blue-800';
            iconPath = '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-1-13a1 1 0 011-1h.01a1 1 0 110 2H10a1 1 0 01-1-1zm1 4a1 1 0 00-1 1v5a1 1 0 001 1h.01a1 1 0 001-1v-5a1 1 0 00-1-1H10z" clip-rule="evenodd" />';
            content = `<span>${message}</span>`;
            break;
        case 'warning':
            typeStyles = 'bg-yellow-100 text-yellow-800';
            iconPath = '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9 7a1 1 0 011-1h.01a1 1 0 011 1v5a1 1 0 01-1 1H10a1 1 0 01-1-1V7zm1 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />';
            content = `<span>${message}</span>`;
            break;
        case 'notification':
            typeStyles = 'bg-purple-100 text-purple-800';
            iconPath = '<path fill-rule="evenodd" d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zm0 16a2 2 0 002-2H8a2 2 0 002 2z" clip-rule="evenodd" />';
            content = `<div class="flex flex-col"><span class="font-bold">${title}</span>`;
            if (message)
                content += '<span>${message}</span>';
            content += '</div>';
            break;
        default:
            typeStyles = 'bg-gray-100 text-gray-800';
            iconPath = '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-1-13a1 1 0 011-1h.01a1 1 0 110 2H10a1 1 0 01-1-1zm1 4a1 1 0 00-1 1v5a1 1 0 001 1h.01a1 1 0 001-1v-5a1 1 0 00-1-1H10z" clip-rule="evenodd" />';
            content = `<span>${message}</span>`;
    }
    notification.className = `p-4 rounded-lg shadow-lg flex items-start space-x-3 transition-all duration-300 transform translate-x-full md:translate-x-0 md:-translate-y-0 opacity-0 ${typeStyles}`;
    notification.innerHTML = `
        <svg class="w-5 h-5 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
            ${iconPath}
        </svg>
        ${content}
    `;

    if (persist_id)
        notification.id = persist_id;

    // Append to container
    const container = document.getElementById('notificationContainer');
    container.appendChild(notification);

    // Animate in
    setTimeout(() => {
        notification.classList.remove('translate-x-full', 'opacity-0');
        notification.classList.add('translate-x-0', 'opacity-100');
    }, 100);

    if (!persist_id) {
        // Auto-dismiss after 3 seconds
        setTimeout(() => {
            // Animate out
            notification.classList.add('translate-x-full', 'opacity-0');
            notification.classList.remove('translate-x-0', 'opacity-100');

            // Remove after animation
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 7000);
    }
}


class WebSocketClient {
    constructor(url, connect_cb=undefined, message_cb=undefined, error_cb=undefined, close_cb=undefined, reconnecting_cb=undefined) {
        this.url = url;
        this.connect_cb = connect_cb;
        this.message_cb = message_cb;
        this.error_cb = error_cb;
        this.close_cb = close_cb;
        this.reconnecting_cb = reconnecting_cb;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.baseDelay = 1000; // Initial delay in ms
        this.maxDelay = 30000; // Max delay in ms
        this.isConnected = false;
        this.connect();
    }

    connect() {
        this.ws = new WebSocket(this.url);

        // Handle open
        this.ws.onopen = () => {

            this.isConnected = true;
            this.reconnectAttempts = 0; // Reset attempts on successful connection
            if (this.connect_cb)
                this.connect_cb()
        };

        // Handle messages
        this.ws.onmessage = (event) => {
            if (this.message_cb)
                this.message_cb(event)
        };

        // Handle errors
        this.ws.onerror = (error) => {
            if (this.error_cb)
                this.error_cb(error)
            this.isConnected = false;
        };

        // Handle close
        this.ws.onclose = () => {
            if (this.close_cb)
                this.close_cb()
            this.isConnected = false;
            this.handleReconnect();
        };
    }

    handleReconnect() {
        if (this.maxReconnectAttempts !== 0 && this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnect attempts reached. Giving up.');
            return;
        }

        // Calculate delay with exponential backoff
        const delay = Math.min(
            this.baseDelay * Math.pow(2, this.reconnectAttempts), // Exponential increase
            this.maxDelay
        );

        if (this.reconnecting_cb)
            this.reconnecting_cb()

        setTimeout(() => {
            this.reconnectAttempts++;
            this.connect();
        }, delay);
    }

    send(message) {
        if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(message);
            return true;
        }
        return false;
    }

    close() {
        this.maxReconnectAttempts = 1;
        this.reconnectAttempts = this.maxReconnectAttempts; // Prevent further reconnects
        if (this.ws) {
            this.ws.close();
        }
    }
}