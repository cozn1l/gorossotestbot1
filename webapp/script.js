// Инициализируем объект Telegram Web App
const tg = window.Telegram.WebApp;

// Настройки
const API_URL = 'https://cozn1l.github.io/gorossotestbot/webapp/'; // ЗАМЕНИТЬ НА СВОЙ URL ПОСЛЕ ЗАГРУЗКИ
const API_BASE_URL = 'https://gorossotestbot.onrender.com/'
const CURRENCY = 'MDL';

// Состояние приложения
let shopData = { categories: [], products: [] };
let currentScreen = 'loader';
let navigationHistory = []; // Для кнопки "назад"
let cart = {}; // { 'product_id_size_color': { item, qty } }

// --- Функции для взаимодействия с API ---
async function fetchShopData() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/all_data`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        shopData = data;
        renderCategories(shopData.categories);
        showScreen('categories-screen');
    } catch (error) {
        console.error("Не удалось загрузить данные магазина:", error);
        document.getElementById('loader').innerHTML = 'Ошибка загрузки магазина.<br>Попробуйте позже.';
    }
}

// --- Функции для отрисовки интерфейса (остаются почти без изменений) ---
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
    currentScreen = screenId;

    if (navigationHistory.length > 0) {
        tg.BackButton.show();
    } else {
        tg.BackButton.hide();
    }
}

function navigateTo(screenId, context) {
    navigationHistory.push({ screen: currentScreen, context: context });
    showScreen(screenId);
}

function goBack() {
    if (navigationHistory.length === 0) return;
    const previous = navigationHistory.pop();
    // Логика возврата к предыдущему экрану
    if (previous.screen === 'categories-screen') {
        renderCategories(shopData.categories);
    } else if (previous.screen === 'products-screen') {
        const cat = shopData.categories.find(c => c.id === previous.context.categoryId);
        renderProducts(previous.context.categoryId, cat ? cat.name : '');
    }
    showScreen(previous.screen);
}

function renderCategories(categories) {
    const list = document.getElementById('categories-list');
    list.innerHTML = '';
    categories.forEach(cat => {
        const item = document.createElement('div');
        item.className = 'item';
        item.innerText = cat.name;
        item.onclick = () => {
            navigationHistory.push({ screen: 'categories-screen' });
            renderProducts(cat.id, cat.name);
        };
        list.appendChild(item);
    });
}

function renderProducts(categoryId, categoryName) {
    document.getElementById('category-title').innerText = categoryName;
    const grid = document.getElementById('products-list');
    grid.innerHTML = '';
    const products = shopData.products.filter(p => p.category_id === categoryId);

    if (products.length === 0) {
        grid.innerHTML = '<p>В этой категории пока нет товаров.</p>';
    } else {
        products.forEach(p => {
            const card = document.createElement('div');
            card.className = 'product-card';
            card.innerHTML = `
                <img src="${p.photo}" alt="${p.name}">
                <div class="product-card-info">
                    <h3>${p.name}</h3>
                    <p>${(p.price / 100).toFixed(2)} ${CURRENCY}</p>
                </div>
            `;
            card.onclick = () => {
                navigationHistory.push({ screen: 'products-screen', context: { categoryId: categoryId, categoryName: categoryName } });
                renderProductDetails(p.id);
            };
            grid.appendChild(card);
        });
    }
    showScreen('products-screen');
}

function renderProductDetails(productId) {
    const product = shopData.products.find(p => p.id === productId);
    const content = document.getElementById('product-details-content');

    const sizesHtml = product.sizes.length > 0
        ? `<div class="options-group"><h4>Размер:</h4>${product.sizes.map(s => `<span class="option-button" data-type="size" data-value="${s}">${s}</span>`).join('')}</div>`
        : '';
    const colorsHtml = product.colors.length > 0
        ? `<div class="options-group"><h4>Цвет:</h4>${product.colors.map(c => `<span class="option-button" data-type="color" data-value="${c}">${c}</span>`).join('')}</div>`
        : '';

    content.innerHTML = `
        <img src="${product.photo}" alt="${product.name}">
        <h2>${product.name}</h2>
        <p><strong>${(product.price / 100).toFixed(2)} ${CURRENCY}</strong></p>
        <p>${product.description}</p>
        ${sizesHtml}
        ${colorsHtml}
        <button id="add-to-cart-btn" class="action-button" onclick='addToCart(${product.id})'>Добавить в корзину</button>
    `;

    document.querySelectorAll('.option-button').forEach(btn => {
        btn.onclick = (e) => {
            const type = e.target.dataset.type;
            document.querySelectorAll(`.option-button[data-type=${type}]`).forEach(b => b.classList.remove('selected'));
            e.target.classList.add('selected');
        };
    });
    showScreen('product-details-screen');
}


// --- Логика корзины (остается без изменений) ---
function addToCart(productId) {
    const product = shopData.products.find(p => p.id === productId);
    const selectedSizeEl = document.querySelector('.option-button[data-type="size"].selected');
    const selectedColorEl = document.querySelector('.option-button[data-type="color"].selected');

    if (product.sizes.length > 0 && !selectedSizeEl) {
        tg.showAlert('Пожалуйста, выберите размер');
        return;
    }
    if (product.colors.length > 0 && !selectedColorEl) {
        tg.showAlert('Пожалуйста, выберите цвет');
        return;
    }

    const size = selectedSizeEl ? selectedSizeEl.dataset.value : '--';
    const color = selectedColorEl ? selectedColorEl.dataset.value : '--';
    const cartKey = `${productId}_${size}_${color}`;

    if (cart[cartKey]) {
        cart[cartKey].qty += 1;
    } else {
        cart[cartKey] = {
            item: { id: product.id, name: product.name, price: product.price, size: size, color: color },
            qty: 1
        };
    }

    tg.HapticFeedback.notificationOccurred('success');
    updateCartCounter();
    tg.showAlert(`${product.name} добавлен в корзину!`);
}

function updateCartCounter() {
    const counter = document.getElementById('cart-counter');
    const totalItems = Object.values(cart).reduce((sum, entry) => sum + entry.qty, 0);
    if (totalItems > 0) {
        counter.innerText = totalItems;
        counter.style.display = 'inline-block';
    } else {
        counter.style.display = 'none';
    }
}

function showCart() {
    navigationHistory.push({ screen: currentScreen }); // Сохраняем текущий экран
    const itemsContainer = document.getElementById('cart-items');
    const totalContainer = document.getElementById('cart-total');
    itemsContainer.innerHTML = '';

    let totalAmount = 0;
    const cartItems = Object.values(cart);

    if (cartItems.length === 0) {
        itemsContainer.innerHTML = '<p>Корзина пуста.</p>';
        totalContainer.innerText = '';
        tg.MainButton.hide();
    } else {
        cartItems.forEach(entry => {
            const cartKey = `${entry.item.id}_${entry.item.size}_${entry.item.color}`;
            itemsContainer.innerHTML += `
                <div class="cart-item">
                    <div class="cart-item-info">
                        <strong>${entry.item.name}</strong><br>
                        <small>${entry.item.size}, ${entry.item.color}</small>
                    </div>
                    <div>${entry.qty} x ${(entry.item.price / 100).toFixed(2)}</div>
                    <div class="cart-item-remove" onclick="removeFromCart('${cartKey}')"> 🗑️ </div>
                </div>`;
            totalAmount += entry.item.price * entry.qty;
        });
        totalContainer.innerText = `Итого: ${(totalAmount / 100).toFixed(2)} ${CURRENCY}`;
        tg.MainButton.setText(`Оплатить ${(totalAmount / 100).toFixed(2)} ${CURRENCY}`);
        tg.MainButton.show();
    }
    showScreen('cart-screen');
}

function removeFromCart(cartKey) {
    delete cart[cartKey];
    showCart();
    updateCartCounter();
}

function showCatalog() {
    navigationHistory = []; // Сбрасываем историю при переходе в каталог
    renderCategories(shopData.categories);
    showScreen('categories-screen');
}


// --- Инициализация ---
window.addEventListener('load', () => {
    tg.ready();
    tg.expand();

    // Загружаем данные с нашего API
    fetchShopData();

    // Обработчик главной кнопки "Оплатить"
    tg.on('mainButtonClicked', () => {
        if (Object.keys(cart).length > 0) {
            tg.sendData(JSON.stringify({ command: 'create_order', cart: cart }));
        }
    });

    // Обработчик системной кнопки "Назад"
    tg.on('backButtonClicked', () => {
        goBack();
    });

    // Переназначаем onclick для кнопок навигации
    document.querySelector('.bottom-nav button:first-child').onclick = showCatalog;
    document.querySelector('.bottom-nav button:nth-child(2)').onclick = showCart;
    document.querySelectorAll('.back-button').forEach(btn => {
        btn.onclick = goBack;
    });
});