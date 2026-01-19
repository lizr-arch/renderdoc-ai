#version 300 es
precision mediump float;

in vec2 v_texcoord;
in vec3 v_worldPos;
in vec3 v_normal;

uniform sampler2D u_diffuseMap;
uniform sampler2D u_normalMap;
uniform vec3 u_lightPos;
uniform vec3 u_viewPos;
uniform vec3 u_lightColor;

out vec4 fragColor;

void main() {
    // Sample textures
    vec4 diffuseColor = texture(u_diffuseMap, v_texcoord);
    vec3 normalTex = texture(u_normalMap, v_texcoord).xyz * 2.0 - 1.0;
    
    // Calculate lighting
    vec3 N = normalize(v_normal + normalTex * 0.3);
    vec3 L = normalize(u_lightPos - v_worldPos);
    vec3 V = normalize(u_viewPos - v_worldPos);
    vec3 H = normalize(L + V);
    
    // Diffuse
    float NdotL = max(dot(N, L), 0.0);
    vec3 diffuse = diffuseColor.rgb * NdotL * u_lightColor;
    
    // Specular (Blinn-Phong)
    float NdotH = max(dot(N, H), 0.0);
    float spec = pow(NdotH, 32.0);
    vec3 specular = u_lightColor * spec * 0.5;
    
    // Ambient
    vec3 ambient = diffuseColor.rgb * 0.1;
    
    fragColor = vec4(ambient + diffuse + specular, diffuseColor.a);
}
