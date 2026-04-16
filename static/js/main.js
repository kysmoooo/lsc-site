/**
 * LS CUSTOMS - GLIFE RP
 * JavaScript Principal
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialisation
    initNavigation();
    initScrollAnimations();
    initRecruitmentForm();
    initModal();
    initScrollEffects();
});

/**
 * Navigation - Gestion du scroll et active state
 */
function initNavigation() {
    const navLinks = document.querySelectorAll('nav a');
    const header = document.querySelector('header');
    
    // Scroll effect pour le header
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            header.style.background = 'rgba(11, 14, 20, 0.98)';
            header.style.boxShadow = '0 2px 20px rgba(0, 0, 0, 0.5)';
        } else {
            header.style.background = 'rgba(11, 14, 20, 0.95)';
            header.style.boxShadow = 'none';
        }
    });
    
    // Smooth scroll pour les liens de navigation
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            const href = link.getAttribute('href');
            if (href.startsWith('#')) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });
}

/**
 * Animations au scroll (Intersection Observer)
 */
function initScrollAnimations() {
    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-fade-in');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Observer les éléments à animer
    const animateElements = document.querySelectorAll('.product-card, .person-card, .direction-card, .stat-card');
    animateElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        observer.observe(el);
    });
}

/**
 * Formulaire de recrutement
 */
function initRecruitmentForm() {
    const recruitForm = document.getElementById('recruitForm');
    
    if (!recruitForm) return;
    
    recruitForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const name = document.getElementById('name').value;
        const dob = document.getElementById('dob').value;
        const rib = document.getElementById('rib').value;
        const tel = document.getElementById('tel').value;
        const exp = document.getElementById('exp').value;
        const dispo = document.getElementById('dispo').value;
        const motivation = document.getElementById('motivation').value;
        const submitBtn = recruitForm.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        
        // Validation
        if (!name || !dob || !rib || !tel || !exp || !dispo || !motivation) {
            showNotification('Veuillez remplir tous les champs', 'error');
            return;
        }
        
        // Loading state
        submitBtn.disabled = true;
        submitBtn.textContent = 'Envoi en cours...';
        
        try {
            const formData = new FormData();
            formData.append('name', name);
            formData.append('dob', dob);
            formData.append('rib', rib);
            formData.append('tel', tel);
            formData.append('exp', exp);
            formData.append('dispo', dispo);
            formData.append('motivation', motivation);
            
            const response = await fetch('/recruit', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                showNotification('Candidature envoyée avec succès!', 'success');
                recruitForm.reset();
                closeModal();
            } else {
                showNotification(data.error || 'Erreur lors de l\'envoi', 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            showNotification('Erreur de connexion', 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    });
}

/**
 * Gestion des modales
 */
function initModal() {
    const modalOverlay = document.querySelector('.modal-overlay');
    const modalClose = document.querySelector('.modal-close');
    const discordBtn = document.querySelector('.discord-btn');
    
    // Ouvrir la modal de connexion
    if (discordBtn && discordBtn.textContent.includes('Rejoindre')) {
        discordBtn.addEventListener('click', () => {
            window.location.href = '/login';
        });
    }
    
    // Fermer la modal
    if (modalClose) {
        modalClose.addEventListener('click', closeModal);
    }
    
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) {
                closeModal();
            }
        });
    }
    
    // Fermer avec Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
        }
    });
}

function openModal() {
    const modalOverlay = document.querySelector('.modal-overlay');
    if (modalOverlay) {
        modalOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal() {
    const modalOverlay = document.querySelector('.modal-overlay');
    if (modalOverlay) {
        modalOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }
}

/**
 * Effets de scroll supplémentaires
 */
function initScrollEffects() {
    // Parallax simple pour le hero
    const hero = document.querySelector('.hero');
    
    if (hero) {
        window.addEventListener('scroll', () => {
            const scrolled = window.pageYOffset;
            const rate = scrolled * 0.3;
            
            if (hero.querySelector('.hero-right')) {
                hero.querySelector('.hero-right').style.transform = 
                    `translateY(${rate}px)`;
            }
        });
    }
    
    // Nombreux éléments au scroll
    const sections = document.querySelectorAll('section');
    
    sections.forEach(section => {
        section.style.opacity = '0';
        section.style.transform = 'translateY(50px)';
        section.style.transition = 'all 0.6s ease';
    });
    
    // Observer pour l'animation des sections
    const sectionObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, { threshold: 0.1 });
    
    sections.forEach(section => {
        sectionObserver.observe(section);
    });
}

/**
 * Notifications toast
 */
function showNotification(message, type = 'info') {
    // Supprimer les notifications existantes
    const existingNotifications = document.querySelectorAll('.notification');
    existingNotifications.forEach(n => n.remove());
    
    // Créer la notification
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()">×</button>
    `;
    
    // Styles dynamiques
    notification.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        padding: 15px 25px;
        border-radius: 10px;
        background: ${type === 'success' ? '#00c853' : type === 'error' ? '#ff1744' : '#2196f3'};
        color: white;
        z-index: 3000;
        animation: slideIn 0.3s ease;
        display: flex;
        align-items: center;
        gap: 15px;
        box-shadow: 0 5px 20px rgba(0, 0, 0, 0.3);
    `;
    
    document.body.appendChild(notification);
    
    // Auto-supprimer après 5 secondes
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

/**
 * API - Charger le personnel dynamiquement
 */
async function loadPersonnel() {
    try {
        const response = await fetch('/api/personnel');
        const personnel = await response.json();
        
        return personnel;
    } catch (error) {
        console.error('Erreur chargement personnel:', error);
        return [];
    }
}

/**
 * Utilitaires
 */
function formatPrice(price) {
    return new Intl.NumberFormat('fr-FR', {
        style: 'currency',
        currency: 'EUR'
    }).format(price);
}

function truncateText(text, maxLength = 100) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

// Ajouter les keyframes pour les animations CSS
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Export pour une utilisation externe
window.LTD = {
    openModal,
    closeModal,
    loadPersonnel,
    formatPrice,
    truncateText,
    showNotification
};

