/**
 * pam_aura.so - PAM module for Aura biometric authentication
 * Communicates with aurad daemon via Unix domain socket
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/time.h>
#include <syslog.h>
#include <security/pam_appl.h>
#include <security/pam_modules.h>
#include <security/pam_ext.h>
#include <errno.h>

// Use dev socket path when AURA_DEV is set
#ifdef AURA_DEV
#define AURA_SOCKET_PATH "/home/anmol/Projects/Aura/run/aura.sock"
#else
#define AURA_SOCKET_PATH "/run/aura/aura.sock"
#endif
#define AUTH_SUCCESS_BYTE 0x01
#define AUTH_FAILURE_BYTE 0x00
#define SOCKET_TIMEOUT_SEC 2
#define MAX_USERNAME_LEN 256

/**
 * Send username to aura daemon and wait for authentication result
 * Returns PAM_SUCCESS on success, PAM_AUTH_ERR on failure
 */
static int aura_verify_user(pam_handle_t *pamh, const char *username)
{
    int sock = -1;
    struct sockaddr_un addr;
    struct timeval tv;
    ssize_t bytes_sent, bytes_read;
    char response = 0;

    /* Create Unix domain socket */
    sock = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sock < 0) {
        pam_syslog(pamh, LOG_ERR, "Failed to create socket: %s", strerror(errno));
        return PAM_AUTH_ERR;
    }

    /* Set receive timeout to prevent hanging */
    tv.tv_sec = SOCKET_TIMEOUT_SEC;
    tv.tv_usec = 0;
    if (setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv)) < 0) {
        pam_syslog(pamh, LOG_ERR, "Failed to set socket timeout: %s", strerror(errno));
        close(sock);
        return PAM_AUTH_ERR;
    }

    /* Configure socket address */
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, AURA_SOCKET_PATH, sizeof(addr.sun_path) - 1);

    /* Connect to daemon */
    if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        pam_syslog(pamh, LOG_NOTICE, "Cannot connect to aura daemon at %s: %s. Falling back to password.",
                   AURA_SOCKET_PATH, strerror(errno));
        close(sock);
        return PAM_AUTH_ERR;
    }

    /* Send username */
    bytes_sent = write(sock, username, strlen(username));
    if (bytes_sent < 0 || (size_t)bytes_sent != strlen(username)) {
        pam_syslog(pamh, LOG_ERR, "Failed to send username: %s", strerror(errno));
        close(sock);
        return PAM_AUTH_ERR;
    }

    /* Read single-byte response */
    bytes_read = read(sock, &response, 1);
    close(sock);

    if (bytes_read != 1) {
        pam_syslog(pamh, LOG_ERR, "Failed to read response from daemon: %s",
                   bytes_read < 0 ? strerror(errno) : "connection closed");
        return PAM_AUTH_ERR;
    }

    if (response == AUTH_SUCCESS_BYTE) {
        pam_syslog(pamh, LOG_INFO, "Aura authentication successful for user: %s", username);
        return PAM_SUCCESS;
    }

    pam_syslog(pamh, LOG_INFO, "Aura authentication failed for user: %s", username);
    return PAM_AUTH_ERR;
}

/* PAM entry point: authentication */
PAM_EXTERN int pam_sm_authenticate(pam_handle_t *pamh, int flags,
                                   int argc, const char **argv)
{
    const char *username = NULL;
    int retval;

    /* Retrieve username */
    retval = pam_get_user(pamh, &username, NULL);
    if (retval != PAM_SUCCESS || username == NULL) {
        pam_syslog(pamh, LOG_ERR, "Failed to get username");
        return PAM_AUTH_ERR;
    }

    /* Skip if user is root (optional, configure via PAM args) */
    if (strcmp(username, "root") == 0) {
        return PAM_AUTH_ERR;
    }

    /* Call aura daemon for verification */
    return aura_verify_user(pamh, username);
}

/* PAM entry point: set credentials (required but no-op for us) */
PAM_EXTERN int pam_sm_setcred(pam_handle_t *pamh, int flags,
                              int argc, const char **argv)
{
    return PAM_SUCCESS;
}

/* PAM entry point: account management */
PAM_EXTERN int pam_sm_acct_mgmt(pam_handle_t *pamh, int flags,
                                int argc, const char **argv)
{
    return PAM_SUCCESS;
}

/* PAM entry point: session management */
PAM_EXTERN int pam_sm_open_session(pam_handle_t *pamh, int flags,
                                   int argc, const char **argv)
{
    return PAM_SUCCESS;
}

PAM_EXTERN int pam_sm_close_session(pam_handle_t *pamh, int flags,
                                    int argc, const char **argv)
{
    return PAM_SUCCESS;
}

/* PAM entry point: password change (not supported) */
PAM_EXTERN int pam_sm_chauthtok(pam_handle_t *pamh, int flags,
                                int argc, const char **argv)
{
    return PAM_SERVICE_ERR;
}