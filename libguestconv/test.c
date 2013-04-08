
#include <stdio.h>
#include "guestconv.h"

int main(int argc, char *argv[])
{
    GuestConv *gc;
    char *description;
    char *database;
    char *drive;

    if (argc != 3) {
        printf("Usage: test <database path> <drive path>\n");
        return 0;
    }

    database = argv[1];
    drive = argv[2];

    gc = guestconv_init(database);
    if (guestconv_err(gc)) {
	fprintf(stderr, "error initializing guestconv: %s\n", gc->error);
	return 1;
    }

    guestconv_add_drive(gc, drive);
    if (guestconv_err(gc)) {
	fprintf(stderr, "error adding drive: %s\n", gc->error);
	return 1;
    }

    description = guestconv_inspect(gc, "rhev");
    if (guestconv_err(gc)) {
	fprintf(stderr, "error getting description: %s\n", gc->error);
	return 1;
    }

    printf("description: %s\n", description);

    guestconv_convert(gc, description);
    if (guestconv_err(gc)) {
	fprintf(stderr, "error performing convert operation: %s\n", gc->error);
	return 1;
    }

    return 0;
}

