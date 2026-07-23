# Deploy στον Hetzner (116.203.100.94)

Ο οδηγός στήνει το Nomos Audit ως **audit.skotanislaw.gr**, δίπλα στο Nomos
One, χωρίς να αγγίξει τις θύρες 80/443 του υπάρχοντος stack: η εφαρμογή
δένει μόνο στο `127.0.0.1:8080` και εκτίθεται δημόσια αποκλειστικά μέσω του
reverse proxy που τερματίζει ήδη το TLS στον server.

## 0. DNS

Προσθέστε A record: `audit.skotanislaw.gr → 116.203.100.94` (TTL 300).

## 1. Εγκατάσταση εφαρμογής

```bash
ssh root@116.203.100.94

# Πρώτη φορά
git clone https://github.com/skotanislaw-design/AppGen-.git /opt/nomos-audit
cd /opt/nomos-audit
cp .env.example .env
nano .env        # συμπληρώστε ANTHROPIC_API_KEY (και προαιρετικά NOMOS_AUDIT_API_KEY)
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

Το script κάνει pull, build, `docker compose up -d` και health check στο
`127.0.0.1:8080/api/health`. Για κάθε **μελλοντική ενημέρωση** αρκεί:

```bash
cd /opt/nomos-audit && ./deploy/deploy.sh
```

## 2. Reverse proxy + SSL

Δείτε ποιος τερματίζει το TLS στον server: `ss -tlnp | grep ':443'`

### Περίπτωση Α — nginx του host (πακέτο συστήματος)

```bash
cp deploy/nginx-audit.conf /etc/nginx/sites-available/audit.skotanislaw.gr
ln -s /etc/nginx/sites-available/audit.skotanislaw.gr /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d audit.skotanislaw.gr   # εκδίδει cert και αναβαθμίζει σε HTTPS
```

### Περίπτωση Β — nginx container του Nomos One (κατέχει τις 80/443)

Το vhost πρέπει να μπει στο δικό του config. Στον φάκελο του Nomos One:

```bash
# 1. Αντιγράψτε το deploy/nginx-audit.conf στον mounted φάκελο conf.d του
#    nginx container — ΜΕ ΜΙΑ ΑΛΛΑΓΗ: το proxy_pass πρέπει να δείχνει στο
#    gateway του docker δικτύου αντί για 127.0.0.1:
#      proxy_pass http://172.17.0.1:8080;
#    (επιβεβαιώστε το gateway με: docker network inspect bridge | grep Gateway)
# 2. Έκδοση cert με τον μηχανισμό certbot που χρησιμοποιεί ήδη το stack
#    (webroot ή certbot container) για το audit.skotanislaw.gr, και προσθήκη
#    του ssl block αντίστοιχα με το nomos.skotanislaw.gr.
# 3. Reload:
docker compose exec nginx nginx -s reload
```

## 3. Επαλήθευση

```bash
curl -s https://audit.skotanislaw.gr/api/health
# {"status":"ok","model":"claude-opus-4-8"}
```

Ανοίξτε https://audit.skotanislaw.gr — καρτέλες «Έλεγχος Δικογράφου» και
«Βιβλιοθήκη Υποδειγμάτων».

## Συστάσεις παραγωγής

- **NOMOS_AUDIT_API_KEY**: ορίστε τιμή στο `.env` ώστε τα endpoints
  ανάλυσης να απαιτούν `Authorization: Bearer` — το εργαλείο καταναλώνει
  Claude tokens και δεν πρέπει να είναι ανοιχτό στο internet. Οι χρήστες
  εισάγουν το κλειδί από το κουμπί «Κλειδί πρόσβασης» της εφαρμογής
  (αποθηκεύεται τοπικά στον περιηγητή και αποστέλλεται ως bearer token).
  Εναλλακτικά ή επιπλέον, περιορίστε την πρόσβαση σε επίπεδο nginx: `allow`
  για τα IP των γραφείων ή HTTP basic auth.
- **Fail2Ban/UFW**: η θύρα 8080 δεν χρειάζεται άνοιγμα στο firewall — μόνο
  80/443 προς τον proxy.
- **Λογαριασμοί χρήσης**: παρακολούθηση κόστους Claude API από το console
  της Anthropic· κάθε πλήρης έλεγχος κάνει 3 κλήσεις Opus.
