// Main JavaScript file for AgroMarket

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    // Enable Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize countdown timers
    initializeCountdowns();
    
    // Auto-refresh bid history for active auctions
    setupAutoRefresh();
    
    // Load market updates
    loadMarketUpdates();
});

// Countdown timer for auctions
function initializeCountdowns() {
    const auctionEndElements = document.querySelectorAll('.auction-end');
    
    auctionEndElements.forEach(element => {
        const endTime = new Date(element.dataset.time).getTime();
        
        function updateCountdown() {
            const now = new Date().getTime();
            const distance = endTime - now;
            
            if (distance < 0) {
                element.innerHTML = 'Auction Ended';
                element.classList.add('text-danger');
                // Trigger auction end check
                checkAuctionEnded(element.dataset.productId);
                return;
            }
            
            const days = Math.floor(distance / (1000 * 60 * 60 * 24));
            const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((distance % (1000 * 60)) / 1000);
            
            let countdownText = '';
            if (days > 0) countdownText += days + 'd ';
            countdownText += hours + 'h ' + minutes + 'm ' + seconds + 's';
            
            element.innerHTML = countdownText;
        }
        
        updateCountdown();
        setInterval(updateCountdown, 1000);
    });
}

function checkAuctionEnded(productId) {
    fetch(`/api/check-auction/${productId}`)
        .then(response => response.json())
        .then(data => {
            if (data.ended) {
                location.reload();
            }
        })
        .catch(error => console.error('Error checking auction:', error));
}

// Auto-refresh setup for bid history
function setupAutoRefresh() {
    const bidHistory = document.querySelector('.bid-history');
    if (bidHistory && bidHistory.dataset.productId) {
        setInterval(() => {
            refreshBidHistory(bidHistory.dataset.productId);
        }, 10000); // Refresh every 10 seconds
    }
}

// Refresh bid history
function refreshBidHistory(productId) {
    fetch(`/api/bids/${productId}`)
        .then(response => response.json())
        .then(data => {
            updateBidHistory(data.bids);
        })
        .catch(error => console.error('Error refreshing bid history:', error));
}

// Load market updates
function loadMarketUpdates() {
    const marketUpdateContainer = document.getElementById('market-updates');
    if (!marketUpdateContainer) return;
    
    fetch('/api/market-updates')
        .then(response => response.json())
        .then(updates => {
            displayMarketUpdates(updates);
        })
        .catch(error => console.error('Error loading market updates:', error));
}

function displayMarketUpdates(updates) {
    const container = document.getElementById('market-updates');
    if (!container) return;
    
    container.innerHTML = '';
    
    updates.forEach(update => {
        const trendIcon = update.trend === 'up' ? '📈' : (update.trend === 'down' ? '📉' : '➡️');
        const trendClass = update.trend === 'up' ? 'text-success' : (update.trend === 'down' ? 'text-danger' : 'text-warning');
        
        const updateElement = document.createElement('div');
        updateElement.className = 'market-update-item mb-3 p-3 border rounded';
        updateElement.innerHTML = `
            <div class="d-flex justify-content-between align-items-start">
                <h6 class="mb-1">${update.title}</h6>
                <small class="text-muted">${update.created_at}</small>
            </div>
            <p class="mb-2 small">${update.content}</p>
            ${update.location ? `<small class="text-muted">📍 ${update.location}</small>` : ''}
            ${update.commodity ? `<br><small class="text-muted">🌾 ${update.commodity}</small>` : ''}
            ${update.price ? `<br><strong class="${trendClass}">${trendIcon} ₹${update.price}</strong>` : ''}
        `;
        container.appendChild(updateElement);
    });
    
    if (updates.length === 0) {
        container.innerHTML = '<p class="text-muted text-center">No market updates available</p>';
    }
}

// Update bid history display
function updateBidHistory(bids) {
    const bidHistory = document.querySelector('.bid-history');
    if (!bidHistory) return;
    
    bidHistory.innerHTML = '';
    
    if (bids.length === 0) {
        bidHistory.innerHTML = '<p class="text-muted">No bids yet</p>';
        return;
    }
    
    bids.forEach(bid => {
        const bidElement = document.createElement('div');
        bidElement.className = 'bid-item mb-2 p-2 border-bottom';
        bidElement.innerHTML = `
            <strong>${bid.buyer}</strong>
            <span class="float-end">₹${parseFloat(bid.amount).toFixed(2)}</span>
            ${bid.quantity ? `<br><small class="text-muted">Quantity: ${bid.quantity}kg</small>` : ''}
            <br>
            <small class="text-muted">${bid.timestamp}</small>
        `;
        bidHistory.appendChild(bidElement);
    });
}

// Form validation for bids with price limits
function validateBidForm(amount, currentPrice, minPrice, maxPrice) {
    if (!amount || amount <= 0) {
        showNotification('Please enter a valid bid amount', 'danger');
        return false;
    }
    
    if (amount <= currentPrice) {
        showNotification('Bid must be higher than current price', 'danger');
        return false;
    }
    
    if (minPrice && amount < minPrice) {
        showNotification(`Minimum bid amount is ₹${minPrice}`, 'danger');
        return false;
    }
    
    if (maxPrice && amount > maxPrice) {
        showNotification(`Maximum bid amount is ₹${maxPrice}`, 'danger');
        return false;
    }
    
    return true;
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
    notification.style.zIndex = '9999';
    notification.style.minWidth = '300px';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// Format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: 2
    }).format(amount);
}

// Search functionality
function searchProducts(query) {
    if (!query || query.length < 2) return;
    
    fetch(`/api/search?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            displaySearchResults(data.products);
        })
        .catch(error => console.error('Error searching products:', error));
}

// Display search results
function displaySearchResults(products) {
    const resultsContainer = document.getElementById('searchResults');
    if (!resultsContainer) return;
    
    resultsContainer.innerHTML = '';
    
    if (products.length === 0) {
        resultsContainer.innerHTML = '<p class="text-muted">No products found</p>';
        return;
    }
    
    products.forEach(product => {
        const productCard = createProductCard(product);
        resultsContainer.appendChild(productCard);
    });
}

// Create product card element
function createProductCard(product) {
    const col = document.createElement('div');
    col.className = 'col-md-4 mb-4';
    
    const imageHtml = product.image ? 
        `<img src="/static/uploads/${product.image}" class="card-img-top" alt="${product.name}" style="height: 200px; object-fit: cover;">` :
        `<div class="card-img-top bg-secondary text-white d-flex align-items-center justify-content-center" style="height: 200px;">
            <i class="bi bi-image" style="font-size: 48px;"></i>
         </div>`;
    
    col.innerHTML = `
        <div class="card h-100">
            ${imageHtml}
            <div class="card-body">
                <h5 class="card-title">${product.name}</h5>
                <p class="card-text">${product.description ? product.description.substring(0, 100) + '...' : 'No description'}</p>
                <ul class="list-unstyled">
                    <li><strong>Available:</strong> ${product.available_quantity} ${product.unit}</li>
                    <li><strong>Current Price:</strong> ₹${parseFloat(product.current_price).toFixed(2)}</li>
                    <li><strong>Farmer:</strong> ${product.farmer}</li>
                </ul>
                <a href="/product/${product.id}" class="btn btn-success">View Details</a>
            </div>
        </div>
    `;
    
    return col;
}

// Handle auction status changes
function updateAuctionStatus(productId, status) {
    const statusElement = document.getElementById(`status-${productId}`);
    if (statusElement) {
        statusElement.className = `badge bg-${status === 'active' ? 'success' : 'secondary'}`;
        statusElement.textContent = status.toUpperCase();
    }
}

// Partial quantity purchase handler
function setupPartialPurchase(productId, maxQuantity, unit, minQuantity) {
    const buyButton = document.getElementById('buy-partial-btn');
    const quantityInput = document.getElementById('partial-quantity');
    const priceInput = document.getElementById('price-per-unit');
    
    if (!buyButton) return;
    
    buyButton.addEventListener('click', () => {
        const quantity = parseFloat(quantityInput.value);
        const price = parseFloat(priceInput.value);
        
        if (isNaN(quantity) || quantity < minQuantity) {
            showNotification(`Minimum purchase quantity is ${minQuantity} ${unit}`, 'danger');
            return;
        }
        
        if (quantity > maxQuantity) {
            showNotification(`Maximum available is ${maxQuantity} ${unit}`, 'danger');
            return;
        }
        
        if (isNaN(price) || price <= 0) {
            showNotification('Please enter a valid price', 'danger');
            return;
        }
        
        fetch(`/buy-partial/${productId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ quantity: quantity, price: price })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, 'success');
                setTimeout(() => location.reload(), 2000);
            } else {
                showNotification(data.error, 'danger');
            }
        })
        .catch(error => {
            showNotification('Error processing purchase', 'danger');
        });
    });
}

// Export functions for use in other scripts
window.AgroMarket = {
    showNotification,
    formatCurrency,
    validateBidForm,
    updateAuctionStatus,
    setupPartialPurchase,
    loadMarketUpdates
};