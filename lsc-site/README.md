# lsc-site

CREATE TABLE IF NOT EXISTS absences (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- TABLES NÉCESSAIRES POUR LE SYSTÈME EMPLOYÉ
-- =============================================

-- Table des employés (séparée des direction_users)
CREATE TABLE IF NOT EXISTS employes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    role VARCHAR(64) DEFAULT 'Employé',
    active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Table des services (prises/fins de service)
CREATE TABLE IF NOT EXISTS services (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employe_id INT NOT NULL,
    employe_name VARCHAR(100) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME DEFAULT NULL,
    duration_minutes INT DEFAULT NULL,
    last_advert_time DATETIME DEFAULT NULL,
    FOREIGN KEY (employe_id) REFERENCES employes(id) ON DELETE CASCADE
);

-- Table des logs d'adverts
CREATE TABLE IF NOT EXISTS advert_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employe_id INT NOT NULL,
    employe_name VARCHAR(100) NOT NULL,
    advert_id INT DEFAULT NULL,
    advert_titre VARCHAR(200) DEFAULT NULL,
    done_at DATETIME NOT NULL,
    FOREIGN KEY (employe_id) REFERENCES employes(id) ON DELETE CASCADE
);

-- Index utiles
CREATE INDEX IF NOT EXISTS idx_services_employe ON services(employe_id);
CREATE INDEX IF NOT EXISTS idx_services_end ON services(end_time);
CREATE INDEX IF NOT EXISTS idx_advert_logs_employe ON advert_logs(employe_id);

-- =============================================
-- ROUTES MANQUANTES à ajouter dans app.py
-- (pour le détail des services par employé)
-- =============================================

-- Route: /api/direction/employes/<emp_id>/services
-- (à ajouter dans app.py — voir ci-dessous)

-- =============================================
-- EXEMPLE D'EMPLOYÉ DE TEST
-- =============================================
-- INSERT INTO employes (username, password_hash, display_name, role)
-- VALUES ('brown_jayden', 'motdepasse123', 'Brown Jayden', 'Mécanicien');