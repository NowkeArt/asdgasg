// Глобальные переменные
let currentUser = null;
let authToken = null;

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    // Проверяем сохраненный токен
    const savedToken = localStorage.getItem('authToken');
    const savedUser = localStorage.getItem('currentUser');
    
    if (savedToken && savedUser) {
        authToken = savedToken;
        currentUser = JSON.parse(savedUser);
        showMainPage();
    } else {
        showAuthPage();
    }

    // Обработчики форм
    setupFormHandlers();
});

// Настройка обработчиков форм
function setupFormHandlers() {
    // Форма входа
    document.getElementById('loginForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = {
            username: formData.get('username'),
            password: formData.get('password')
        };

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            
            if (response.ok) {
                authToken = result.token;
                currentUser = result.user;
                localStorage.setItem('authToken', authToken);
                localStorage.setItem('currentUser', JSON.stringify(currentUser));
                showMainPage();
            } else {
                alert(result.error || 'Ошибка входа');
            }
        } catch (error) {
            alert('Ошибка соединения');
        }
    });

    // Форма регистрации
    document.getElementById('registerForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = {
            username: formData.get('username'),
            email: formData.get('email'),
            password: formData.get('password')
        };

        try {
            const response = await fetch('/api/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            
            if (response.ok) {
                authToken = result.token;
                currentUser = result.user;
                localStorage.setItem('authToken', authToken);
                localStorage.setItem('currentUser', JSON.stringify(currentUser));
                showMainPage();
            } else {
                alert(result.error || 'Ошибка регистрации');
            }
        } catch (error) {
            alert('Ошибка соединения');
        }
    });

    // Форма создания ТЗ
    document.getElementById('createTaskForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);

        try {
            const response = await fetch('/api/tasks', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${authToken}` },
                body: formData
            });

            const result = await response.json();
            
            if (response.ok) {
                closeModal('createTaskModal');
                e.target.reset();
                loadTasks();
                alert('ТЗ успешно создано!');
            } else {
                alert(result.error || 'Ошибка создания ТЗ');
            }
        } catch (error) {
            alert('Ошибка соединения');
        }
    });

    // Форма создания бага
    document.getElementById('createBugForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);

        try {
            const response = await fetch('/api/bugs', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${authToken}` },
                body: formData
            });

            const result = await response.json();
            
            if (response.ok) {
                closeModal('createBugModal');
                e.target.reset();
                loadBugs();
                alert('Отчет о баге отправлен!');
            } else {
                alert(result.error || 'Ошибка отправки отчета');
            }
        } catch (error) {
            alert('Ошибка соединения');
        }
    });

    // Форма создания заявки
    document.getElementById('createApplicationForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        
        const data = {
            position: formData.get('position'),
            answers: [
                formData.get('timezone'),
                formData.get('moderation_experience'),
                formData.get('other_projects'),
                formData.get('cheat_check_knowledge'),
                formData.get('grif_experience'),
                formData.get('age'),
                formData.get('available_time')
            ]
        };

        try {
            const response = await fetch('/api/applications', {
                method: 'POST',
                headers: { 
                    'Authorization': `Bearer ${authToken}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            
            if (response.ok) {
                closeModal('createApplicationModal');
                e.target.reset();
                loadApplications();
                alert('Заявка подана успешно!');
            } else {
                alert(result.error || 'Ошибка подачи заявки');
            }
        } catch (error) {
            alert('Ошибка соединения');
        }
    });
}

// Переключение вкладок авторизации
function switchAuthTab(tab) {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const tabs = document.querySelectorAll('.auth-tab');

    tabs.forEach(t => t.classList.remove('active'));
    
    if (tab === 'login') {
        loginForm.classList.remove('hidden');
        registerForm.classList.add('hidden');
        tabs[0].classList.add('active');
    } else {
        loginForm.classList.add('hidden');
        registerForm.classList.remove('hidden');
        tabs[1].classList.add('active');
    }
}

// Показать страницу авторизации
function showAuthPage() {
    document.getElementById('authPage').classList.remove('hidden');
    document.getElementById('mainPage').classList.add('hidden');
}

// Показать основную страницу
function showMainPage() {
    document.getElementById('authPage').classList.add('hidden');
    document.getElementById('mainPage').classList.remove('hidden');
    document.getElementById('username').textContent = currentUser.username;
    
    // Загружаем данные
    loadTasks();
    loadBugs();
    loadApplications();
}

// Выход
function logout() {
    localStorage.removeItem('authToken');
    localStorage.removeItem('currentUser');
    authToken = null;
    currentUser = null;
    showAuthPage();
}

// Переключение вкладок
function switchTab(tab) {
    // Убираем активный класс со всех вкладок
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.add('hidden'));
    
    // Активируем нужную вкладку
    event.target.classList.add('active');
    document.getElementById(tab + 'Tab').classList.remove('hidden');
}

// Модальные окна
function showCreateTaskModal() {
    document.getElementById('createTaskModal').classList.add('show');
}

function showCreateBugModal() {
    document.getElementById('createBugModal').classList.add('show');
}

function showCreateApplicationModal() {
    document.getElementById('createApplicationModal').classList.add('show');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('show');
}

// Загрузка ТЗ
async function loadTasks() {
    const statusFilter = document.getElementById('taskStatusFilter').value;
    const url = statusFilter ? `/api/tasks?status=${statusFilter}` : '/api/tasks';
    
    try {
        const response = await fetch(url, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        const tasks = await response.json();
        const tasksList = document.getElementById('tasksList');
        
        if (tasks.length === 0) {
            tasksList.innerHTML = '<p style="text-align: center; color: #666;">Нет ТЗ для отображения</p>';
            return;
        }
        
        tasksList.innerHTML = tasks.map(task => `
            <div class="task-item">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                    <div>
                        <strong>ТЗ #${task.id}</strong>
                        <span class="status-badge status-${task.status}">${getStatusText(task.status)}</span>
                    </div>
                    <small style="color: #666;">${formatDate(task.created_at)}</small>
                </div>
                <p><strong>Автор:</strong> ${task.author_username}</p>
                <p><strong>Описание:</strong> ${task.description}</p>
                ${task.media_file_id ? `<img src="/uploads/${task.media_file_id}" class="media-preview" alt="Медиафайл">` : ''}
                ${task.assigned_admin_username ? `<p><strong>Назначен:</strong> ${task.assigned_admin_username}</p>` : ''}
                ${currentUser.role === 'admin' || currentUser.role === 'super_admin' ? `
                    <div style="margin-top: 15px;">
                        <button class="btn btn-success" onclick="updateTaskStatus(${task.id}, 'completed')">
                            <i class="fas fa-check"></i> Выполнить
                        </button>
                        <button class="btn btn-danger" onclick="updateTaskStatus(${task.id}, 'rejected')">
                            <i class="fas fa-times"></i> Отклонить
                        </button>
                    </div>
                ` : ''}
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка загрузки ТЗ:', error);
    }
}

// Загрузка багов
async function loadBugs() {
    try {
        const response = await fetch('/api/bugs', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        const bugs = await response.json();
        const bugsList = document.getElementById('bugsList');
        
        if (bugs.length === 0) {
            bugsList.innerHTML = '<p style="text-align: center; color: #666;">Нет отчетов о багах</p>';
            return;
        }
        
        bugsList.innerHTML = bugs.map(bug => `
            <div class="bug-item">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                    <div>
                        <strong>Баг #${bug.id}</strong>
                        <span class="status-badge status-${bug.status}">${getStatusText(bug.status)}</span>
                    </div>
                    <small style="color: #666;">${formatDate(bug.created_at)}</small>
                </div>
                <p><strong>Автор:</strong> ${bug.author_username}</p>
                <p><strong>Описание:</strong> ${bug.description}</p>
                ${bug.media_file_id ? `<img src="/uploads/${bug.media_file_id}" class="media-preview" alt="Скриншот">` : ''}
                ${bug.assigned_admin_username ? `<p><strong>Назначен:</strong> ${bug.assigned_admin_username}</p>` : ''}
                ${currentUser.role === 'admin' || currentUser.role === 'super_admin' ? `
                    <div style="margin-top: 15px;">
                        <button class="btn btn-warning" onclick="updateBugStatus(${bug.id}, 'in_progress')">
                            <i class="fas fa-cog"></i> В работе
                        </button>
                        <button class="btn btn-success" onclick="updateBugStatus(${bug.id}, 'completed')">
                            <i class="fas fa-check"></i> Исправлено
                        </button>
                        <button class="btn btn-danger" onclick="updateBugStatus(${bug.id}, 'rejected')">
                            <i class="fas fa-times"></i> Отклонить
                        </button>
                    </div>
                ` : ''}
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка загрузки багов:', error);
    }
}

// Загрузка заявок
async function loadApplications() {
    try {
        const response = await fetch('/api/applications', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        const applications = await response.json();
        const applicationsList = document.getElementById('applicationsList');
        
        if (applications.length === 0) {
            applicationsList.innerHTML = '<p style="text-align: center; color: #666;">Нет заявок</p>';
            return;
        }
        
        const questions = [
            "1. Ваш часовой пояс?",
            "2. Есть ли опыт модерации? Если да, то укажите проект и длительность поста.",
            "3. Состоите ли Вы на данный момент в администрации/модерации/команде на ином проекте?",
            "4. Знаете ли Вы, как проводить проверку на читы?",
            "5. Общий Опыт/Длительность игры на серверах типу Анка/Гриф?",
            "6. Ваш возраст?",
            "7. Время, которое вы готовы выделять на сервер в день (можно указать промежуток времени и дни)."
        ];
        
        applicationsList.innerHTML = applications.map(app => `
            <div class="app-item">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px;">
                    <div>
                        <strong>Заявка #${app.id} на должность: ${app.position}</strong>
                        <span class="status-badge status-${app.status}">${getStatusText(app.status)}</span>
                    </div>
                    <small style="color: #666;">${formatDate(app.created_at)}</small>
                </div>
                <p><strong>Кандидат:</strong> ${app.username}</p>
                
                <ul class="questions-list">
                    <li>
                        <div class="question-text">${questions[0]}</div>
                        <div class="answer-text">${app.timezone}</div>
                    </li>
                    <li>
                        <div class="question-text">${questions[1]}</div>
                        <div class="answer-text">${app.moderation_experience}</div>
                    </li>
                    <li>
                        <div class="question-text">${questions[2]}</div>
                        <div class="answer-text">${app.other_projects}</div>
                    </li>
                    <li>
                        <div class="question-text">${questions[3]}</div>
                        <div class="answer-text">${app.cheat_check_knowledge}</div>
                    </li>
                    <li>
                        <div class="question-text">${questions[4]}</div>
                        <div class="answer-text">${app.grif_experience}</div>
                    </li>
                    <li>
                        <div class="question-text">${questions[5]}</div>
                        <div class="answer-text">${app.age}</div>
                    </li>
                    <li>
                        <div class="question-text">${questions[6]}</div>
                        <div class="answer-text">${app.available_time}</div>
                    </li>
                </ul>
                
                ${currentUser.role === 'admin' || currentUser.role === 'super_admin' ? `
                    <div style="margin-top: 15px;">
                        <button class="btn btn-success" onclick="updateApplicationStatus(${app.id}, 'approved')">
                            <i class="fas fa-check"></i> Одобрить
                        </button>
                        <button class="btn btn-danger" onclick="updateApplicationStatus(${app.id}, 'rejected')">
                            <i class="fas fa-times"></i> Отклонить
                        </button>
                    </div>
                ` : ''}
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка загрузки заявок:', error);
    }
}

// Обновление статуса ТЗ
async function updateTaskStatus(taskId, status) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/status`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ status })
        });

        if (response.ok) {
            loadTasks();
            alert('Статус ТЗ обновлен!');
        } else {
            alert('Ошибка обновления статуса');
        }
    } catch (error) {
        alert('Ошибка соединения');
    }
}

// Обновление статуса бага
async function updateBugStatus(bugId, status) {
    try {
        const response = await fetch(`/api/bugs/${bugId}/status`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ status })
        });

        if (response.ok) {
            loadBugs();
            alert('Статус бага обновлен!');
        } else {
            alert('Ошибка обновления статуса');
        }
    } catch (error) {
        alert('Ошибка соединения');
    }
}

// Обновление статуса заявки
async function updateApplicationStatus(appId, status) {
    try {
        const response = await fetch(`/api/applications/${appId}/status`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ status })
        });

        if (response.ok) {
            loadApplications();
            alert('Статус заявки обновлен!');
        } else {
            alert('Ошибка обновления статуса');
        }
    } catch (error) {
        alert('Ошибка соединения');
    }
}

// Вспомогательные функции
function getStatusText(status) {
    const statusMap = {
        'pending': 'Ожидает',
        'completed': 'Выполнено',
        'rejected': 'Отклонено',
        'in_progress': 'В работе',
        'approved': 'Одобрено'
    };
    return statusMap[status] || status;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('ru-RU');
}

// Закрытие модальных окон по клику вне их
window.addEventListener('click', function(event) {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        if (event.target === modal) {
            modal.classList.remove('show');
        }
    });
});