# OpenCode Sandbox

Wrapper per eseguire OpenCode in un container Podman rootless, mantenendo
workspace e configurazione persistenti tra le sessioni.

## Prerequisiti

- Linux o WSL2
- Podman rootless
- `systemd --user` opzionale, solo per il socket API Podman

Verifica il runtime:

```bash
podman info --format '{{.Host.Security.Rootless}}'
```

Il comando deve restituire `true`.

## Installazione

Rendi eseguibile il wrapper:

```bash
chmod 0755 /mnt/d/Workspace/opencode-container/opencode-wrapper
```

Aggiungi l'alias alla configurazione della shell:

```bash
alias opencode='/mnt/d/Workspace/opencode-container/opencode-wrapper'
```

Ricarica la configurazione della shell oppure apri una nuova sessione.

## Utilizzo

Il wrapper mantiene il comportamento normale di OpenCode:

```bash
cd /home/yari/Workspace/progetto
opencode
opencode --version
opencode run "Descrivi questo progetto"
```

La prima esecuzione costruisce l'immagine. La versione predefinita è `1.18.3`
ed è possibile sovrascriverla per una sessione:

```bash
OPENCODE_VERSION=1.18.3 opencode --version
```

## Nomi Dei Container

Il nome deriva dal basename del workspace:

```text
/home/yari/Workspace/progetto -> progetto-0
```

Le istanze successive usano l'indice massimo esistente più uno. Gli indici
intermedi non vengono riutilizzati finché esiste un indice superiore.

I container sono effimeri e vengono rimossi al termine della sessione.

## Socket Podman Opzionale

OpenCode si avvia anche senza il socket API Podman. In questo caso non potrà
lanciare container secondari e il wrapper mostrerà i comandi per abilitarlo.
L'immagine include `podman-remote` esposto anche come comando `podman`; il
comando funziona solo quando il socket API è montato.

Abilitazione solo per la sessione corrente:

```bash
systemctl --user start podman.socket
```

Abilitazione automatica all'accesso:

```bash
systemctl --user enable --now podman.socket
```

Il wrapper non esegue automaticamente questi comandi.

## Percorsi Montati

In scrittura:

- workspace corrente;
- `~/.config/opencode`;
- `~/.local/share/opencode`;
- `~/.cache/opencode`;
- `~/.local/state/opencode`.

In sola lettura, se presenti:

- `~/.claude`;
- `~/.agents`;
- `/etc/opencode`.

La home completa, `.ssh`, `.aws`, `.docker`, il `.gitconfig` globale e la
configurazione Podman non vengono montati.

## Sicurezza

Il container principale viene eseguito con:

- root filesystem read-only;
- UID/GID dell'utente host;
- user namespace `keep-id`;
- tutte le capability rimosse;
- `no-new-privileges`;
- `/tmp` temporaneo con `nosuid` e `nodev`; deve restare eseguibile perché
  OpenTUI carica da qui una libreria condivisa all'avvio;
- limite al numero di processi.

Il socket Podman rootless concede comunque a OpenCode il pieno controllo del
Podman dell'utente. Un processo che usa volontariamente l'API può accedere ai
percorsi host leggibili dall'utente. Per il massimo isolamento, non abilitare
il socket.

## Aggiornamento

La versione è fissata in `opencode-wrapper` tramite `OPENCODE_VERSION` e nel
`Dockerfile` tramite `ARG OPENCODE_VERSION`.

Per aggiornare:

1. modifica entrambi i valori alla nuova versione;
2. rimuovi o ricostruisci il tag immagine precedente;
3. verifica `opencode --version`.

Non usare `opencode upgrade` dentro il container: il filesystem principale è
immutabile.
