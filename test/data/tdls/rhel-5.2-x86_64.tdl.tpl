<template>
  <name>rhel-5.2-x86_64</name>

  <os>
    <name>RHEL-5</name>
    <version>U2</version>
    <arch>x86_64</arch>
    <install type='iso'>
      <iso>{{iso_repository}}/rhel-5.2-server-x86_64-dvd.iso</iso>
    </install>
    <rootpw>password</rootpw>
  </os>

  <description>RHEL 5.2 x86_64</description>

  <packages>
    <package name="openssh-server"/>
  </packages>

  <files>
    <file name="/home/guest/.ssh/authorized_keys"><![CDATA[#!/bin/bash
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDMqVhtTLpyrxMQSdsWMnKy3JWqBLkQblQ++7cZtPBtinZ/RpgTUudQkFOGnjHP+UTccboe09mIc7RF31hgDQkwgapTIJj6enLymdXn+TfHywY1tsyxS1wJ0oMaNoaEm2grdK8UIFHyTt5uH2HC3iIeLomKtCadYEp+1Er7484PKIs4z1sq0tclgvKwVMcvw9xlkx/NqhC7t9EmKnyQziGoroHY8lcSri3a8WJ1WQWyq2sfR4pJ+j0Hq88Hn3OIUCYs5DcGRS0IZy8mgN9oQWcWZYTMLUhsdv6od18BK7U1gcjkvgTmNcr5DMTYrB2BwxIXqCGVdoaXHE3uTMvo3ETb guest@localhost.localdomain
]]>
    </file>
  </files>

  <commands>
    <command name="create_guest">useradd guest</command>
  </commands>
</template>
