
#include <stdio.h>
#include "guestconv.h"

int main (void)
{
    GuestConv *gc;
    char *description;

    gc = guestconv_init("/home/imain/src/guestconv/conf/guestconv.db");
    if (guestconv_err(gc)) {
	fprintf(stderr, "error initializing guestconv: %s\n", gc->error);
	return 1;
    }
    
    printf("gc is %p\n", gc);

    guestconv_add_drive(gc, "/home/imain/tmp/Fedora18-Cloud-x86_64-20130115.raw");
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

