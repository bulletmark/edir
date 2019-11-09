#!/bin/bash
# Script to install or uninstall python package in current dir

usage() {
    echo "Usage: $(basename $0) [-options]"
    echo "Options:"
    echo "-d <destdir> (alternative root dir)"
    echo "-u <package> (uninstall given package name)"
    echo "-o <optimise_level> (default=1)"
    exit 1
}

DESTDIR=""
NAME=""
OPTLEVEL="1"
while getopts d:u:o:\? c; do
    case $c in
    d) DESTDIR="$OPTARG";;
    u) NAME="$OPTARG";;
    o) OPTLEVEL="$OPTARG";;
    ?) usage;;
    esac
done

shift $((OPTIND - 1))

if [[ $# -ne 0 ]]; then
    usage
fi

if [[ -z "$NAME" ]]; then
    if [[ -n "$DESTDIR" ]]; then
	DESTDIR="--root=$DESTDIR"
    fi
    if [[ -n "$OPTLEVEL" ]]; then
	OPTLEVEL="--optimize=$OPTLEVEL"
    fi
    exec python3 setup.py install $DESTDIR $OPTLEVEL
fi

rm -vrf $DESTDIR/etc/$NAME.conf $DESTDIR/usr/local/etc/$NAME.conf

for d in "" "/local"; do
    rm -vrf \
	$DESTDIR/usr$d/bin/$NAME \
	$DESTDIR/usr$d/bin/$NAME-* \
	$DESTDIR/usr$d/share/doc/$NAME \
	;
    for sd in site dist; do
	rm -vrf \
	    $DESTDIR/usr$d/lib/python*/$sd-packages/$NAME.* \
	    $DESTDIR/usr$d/lib/python*/$sd-packages/$NAME-* \
	    $DESTDIR/usr$d/lib/python*/$sd-packages/__pycache__/$NAME.* \
	    ;
    done
done
