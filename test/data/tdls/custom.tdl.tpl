<template>
  <name>{{name}}</name>
  <os>
    <name>{{os['name']}}</name>
    <version>{{os['version']}}</version>
    <arch>{{os['arch']}}</arch>
    <install type='url'>
      <url>{{os['install_url']}}</url>
    </install>
  </os>
  <description>{{description}}</description>

  <packages>
    {% for pkg in packages %}
    <package>
      <package name="{{pkg }}" />
    </package>
    {% endfor %}
  </packages>

  <!-- TODO files, commands, etc -->
</template>
