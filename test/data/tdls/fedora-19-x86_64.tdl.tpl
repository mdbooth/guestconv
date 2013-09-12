<template>
  <name>f19jeos</name>
  <os>
    <name>Fedora</name>
    <version>19</version>
    <arch>x86_64</arch>
    <install type='url'>
      <url>{{fedora_mirror}}/releases/19/Fedora/x86_64/os/</url>
    </install>
  </os>
  <description>Fedora 19</description>

  <repositories>
    <repository name='fedora'>
      <url>{{fedora_mirror}}/releases/19/Everything/x86_64/os</url>
      <signed>no</signed><!-- oz doesn't install the gpg key automatically -->
    </repository>
    <repository name='fedora-updates'>
      <url>{{fedora_mirror}}/updates/19/x86_64</url>
      <signed>no</signed><!-- oz doesn't install the gpg key automatically -->
    </repository>
  </repositories>

  <packages>
    <package name='openssh-server'/>
    <package name='xorg-x11-drv-cirrus'/>
    <package name='xorg-x11-drv-qxl'/>
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
