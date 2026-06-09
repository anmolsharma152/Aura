# Makefile for pam_aura.so
# Build: make
# Build for dev: make dev
# Install: sudo make install
# Test: make test

CC = gcc
CFLAGS = -fPIC -Wall -Wextra -O2 -std=c11 -D_GNU_SOURCE
LDFLAGS = -shared -lpam

# PAM module directory (adjust for your distro)
PAM_MOD_DIR = /lib/security

TARGET = pam_aura.so
SRC = pam_aura.c

all: $(TARGET)

dev: CFLAGS += -DAURA_DEV
dev: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Install PAM module to system directory
install: $(TARGET)
	install -D -m 644 $(TARGET) $(DESTDIR)$(PAM_MOD_DIR)/$(TARGET)

# Remove installed module
uninstall:
	rm -f $(DESTDIR)$(PAM_MOD_DIR)/$(TARGET)

# Test compilation only (no install)
test: $(TARGET)
	@echo "PAM module compiled successfully: $(TARGET)"
	@file $(TARGET)
	@ldd $(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all dev install uninstall test clean