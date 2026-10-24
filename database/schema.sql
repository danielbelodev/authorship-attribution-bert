CREATE DATABASE IF NOT EXISTS diplomarbeit CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE diplomarbeit;

-- Tabelle für Autoren erstellen
CREATE TABLE authors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE
);

-- Tabelle für Artikel erstellen
CREATE TABLE articles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    url TEXT NOT NULL,
    lastmod DATETIME NOT NULL,
    content LONGTEXT NOT NULL
);

-- Verknüpfungstabelle Artikel <-> Autoren (n:m, ein Artikel kann mehrere Autoren haben)
CREATE TABLE placeholder (
    article_id INT,
    author_id INT,
    PRIMARY KEY (article_id, author_id),
    FOREIGN KEY (article_id) REFERENCES articles(id),
    FOREIGN KEY (author_id) REFERENCES authors(id)
);
