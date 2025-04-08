#!/usr/local/bin/perl
#
# Make compilation request to compilation API.
#
# Accepts newer article id and optionally the compiler 
# API ip address.
#
# ex. 'compile_announced.pl 2012.02375'
#

use strict;

my $verbose = 0;

if ($verbose) {print "$ARGV[0]\n";}

my $host_ip = $ARGV[1] || "34.75.4.221";

my $article_id = $ARGV[0];

if (! $ENV{JWT}) {
  print ("You must set JWT environment variable.\n");
  exit;
}

my $line = `curl -s -I https://arxiv.org/src/$article_id`;

my $etag_line = `curl -s -I https://arxiv.org/src/$article_id | grep ETag`;

$etag_line =~ /ETag:\s(.*)/;
my $etag = $1;

if ($etag && $verbose) {
  print "Found ETag: $etag\n";
}

$etag =~ /\"(.*)\"/;

my $clean_etag = $1;

my $command = "curl -s -XPOST -i -H \"Authorization: $ENV{JWT}\"  -d '{\"source_id\":";
$command .= "\"$article_id\",\"checksum\":\"\\\"$clean_etag\\\"\"";
$command .= ",\"format\":\"pdf\",\"force\":1}' http://$host_ip:80/";

if ($verbose){
  print "Command: $command\n\n";
}

my $resp = `$command`;

if ($verbose) {print ("Response: $resp\n");}

# Response looks like this
#
#  Response: HTTP/1.1 202 ACCEPTED
#  Content-Type: application/json
#  Content-Length: 3
#  Location: http://34.75.4.221/2012.02375/Ik1vbiwgMDcgRGVjIDIwMjAgMDE6MDk6MTUgR01UIg%3D%3D/pdf

if ($resp =~ /ACCEPTED/) {

  print ("\nCompilation request was ACCEPTED\n");

  if ($resp =~ /Location: (.*)/) {
    my $loc = $1;
    print ("\nURL to check status:\n\n  $loc\n");
    # Strange character gets inserted into location
    #my $command = "curl -i -H \"Authorization: $ENV{JWT}\" $loc";
    my $command = "curl -i -H \"Authorization: \$JWT\" URL";
    print ("\nUse command \n\t'$command'\nto get status\n");
    print ("\n\tAdd '/product' to URL if you want PDF content\n\n");
    #print `$command`;
  } else {
    print ("Location not returned\n");
  }

} else {
  print ("Compilation request FAILED: \n$resp\n");
}
