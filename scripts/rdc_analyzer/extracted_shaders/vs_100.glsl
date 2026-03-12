#version 300 es
precision highp float;

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec2 a_texcoord;
layout(location = 2) in vec3 a_normal;

uniform mat4 u_mvpMatrix;
uniform mat4 u_modelMatrix;
uniform mat3 u_normalMatrix;

out vec2 v_texcoord;
out vec3 v_worldPos;
out vec3 v_normal;

void main() {
    vec4 worldPos = u_modelMatrix * vec4(a_position, 1.0);
    v_worldPos = worldPos.xyz;
    v_normal = normalize(u_normalMatrix * a_normal);
    v_texcoord = a_texcoord;
    gl_Position = u_mvpMatrix * vec4(a_position, 1.0);
}
