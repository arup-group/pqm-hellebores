// version.c: C translation of version.py
// Compile with: gcc -o version version.c -lssl -lcrypto
// Usage: version [--increment_sub_version]

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>
#include <openssl/sha.h>

#define VERSION_FILE "../VERSION"
#define PROGRAM_DIR "../pqm"
#define PICO_DIR "../pico"
#define RUN_DIR "../run"

void get_version(char *out, size_t out_size) {
    FILE *f = fopen(VERSION_FILE, "r");
    if (!f) {
        snprintf(out, out_size, "unknown");
        return;
    }
    fgets(out, out_size, f);
    fclose(f);
    size_t len = strlen(out);
    if (len > 0 && out[len-1] == '\n') out[len-1] = '\0';
}

void set_version(const char *new_version) {
    FILE *f = fopen(VERSION_FILE, "w");
    if (!f) return;
    fprintf(f, "%s\n", new_version);
    fclose(f);
}

void list_files(const char *dir, char files[][256], int *count) {
    DIR *d = opendir(dir);
    struct dirent *entry;
    *count = 0;
    if (!d) return;
    while ((entry = readdir(d)) != NULL) {
        if (entry->d_type == DT_REG && entry->d_name[0] != '.') {
            snprintf(files[*count], 256, "%s/%s", dir, entry->d_name);
            (*count)++;
        }
    }
    closedir(d);
}

void readfiles(char files[][256], int count, char *out, size_t out_size) {
    out[0] = '\0';
    for (int i = 0; i < count; ++i) {
        FILE *f = fopen(files[i], "r");
        if (!f) continue;
        char buf[1024];
        while (fgets(buf, sizeof(buf), f)) {
            strncat(out, buf, out_size - strlen(out) - 1);
        }
        fclose(f);
    }
}

void sha256sum(char files[][256], int count, char *out, size_t out_size) {
    char contents[65536] = "";
    readfiles(files, count, contents, sizeof(contents));
    unsigned char hash[SHA256_DIGEST_LENGTH];
    SHA256((unsigned char*)contents, strlen(contents), hash);
    for (int i = 0; i < SHA256_DIGEST_LENGTH; ++i) {
        sprintf(out + i*2, "%02x", hash[i]);
    }
    out[SHA256_DIGEST_LENGTH*2] = '\0';
}

void git_branch(char *out, size_t out_size) {
    FILE *fp = popen("git rev-parse --abbrev-ref HEAD", "r");
    if (!fp) { snprintf(out, out_size, "unknown"); return; }
    fgets(out, out_size, fp);
    pclose(fp);
    size_t len = strlen(out);
    if (len > 0 && out[len-1] == '\n') out[len-1] = '\0';
}

void git_head(char *out, size_t out_size) {
    FILE *fp = popen("git rev-parse HEAD", "r");
    if (!fp) { snprintf(out, out_size, "unknown"); return; }
    fgets(out, out_size, fp);
    pclose(fp);
    size_t len = strlen(out);
    if (len > 0 && out[len-1] == '\n') out[len-1] = '\0';
}

void increment_sub_version() {
    char ver[128];
    get_version(ver, sizeof(ver));
    int major, minor, sub;
    char codename[64] = "";
    if (sscanf(ver, "%d.%d.%d%63s", &major, &minor, &sub, codename) == 4) {
        if (sub < 999) sub++;
        char newver[128];
        snprintf(newver, sizeof(newver), "%d.%d.%03d%s", major, minor, sub, codename);
        set_version(newver);
        printf("%s\n", newver);
    } else {
        printf("Failed to increment sub-version\n");
    }
}

int main(int argc, char *argv[]) {
    int inc = 0;
    if (argc > 1 && strcmp(argv[1], "--increment_sub_version") == 0) inc = 1;
    if (inc) {
        increment_sub_version();
        return 0;
    }
    char ver[128], branch[128], head[128];
    get_version(ver, sizeof(ver));
    git_branch(branch, sizeof(branch));
    git_head(head, sizeof(head));
    printf("Version              : %s\n", ver);
    printf("Git branch           : %s\n", branch);
    printf("Git commit id        : %s\n", head);
    // List files and show sha256
    char files[128][256];
    int count = 0;
    list_files(PROGRAM_DIR, files, &count);
    list_files(PICO_DIR, files + count, &count);
    list_files(RUN_DIR, files + count, &count);
    char sha[SHA256_DIGEST_LENGTH*2+1];
    sha256sum(files, count, sha, sizeof(sha));
    printf("SHA256 of files      : %s\n", sha);
    return 0;
}
