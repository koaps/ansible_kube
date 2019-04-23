# Ansible Kubectl Module

This is a module for working with kubectl from Ansible.

It can be used to do simple kubectl commands or more complicated filtering on the outputs.

### applying a manifest by directory
```
- name: apply kube-dashboard configs files
  kube:
    filename: "{{ manifest_path }}/kube-dashboard/"
```

### applying a manifest by file
```
- name: apply kube-dns configs files
  kube:
    filename: "{{ manifest_path }}/kube-dns/{{ k_file }}"
  loop:
    - kube-dns-config-map.json
    - kube-dns-deployment.json
    - kube-dns-service-account.json
    - kube-dns-service.json
  loop_control:
    loop_var: k_file
```

### creating secrets
```
- name: create basic-auth secret
  kube:
    command: create
    resource:
      - secret
      - generic
    name: basic-auth
    namespace: ingress-nginx
    keyvars: "--from-file=auth={{ manifest_path }}/ingress_auth"
```

```
- name: create tls secret
  kube:
    command: create
    resource:
      - secret
      - tls
    name: kubernetes-nginx-certs
    namespace: ingress-nginx
    keyvars:
      - "--cert={{ ssl_cert_dir }}/nginx.cert.pem"
      - "--key={{ ssl_private_dir }}/nginx.key.pem"
```

### labeling masters
```
- name: label masters
  block:
    - name: get labeled masters
      kube:
        command: get
        resource: node
        label: node-role.kubernetes.io/master
        keyvars: --output=name
      register: m_labels

    - name: label masters
      kube:
        command: label
        resource: node
        name: "{{ m_name }}"
        keyvars: node-role.kubernetes.io/master=
        overwrite: true
      loop: "{{ masters }}"
      loop_control:
        index_var: m_idx
        loop_var: m_ip
      vars:
        m_name: "{{ master_prefix }}{{ m_idx }}.{{ dns_suffix_internal }}"
      when: "{{ m_name not in (m_labels.meta | regex_replace('node/','')) }}"
```

### waiting for nodes to be ready
This waits until the count of ready masters matches the masters array length for a list like ['master1', 'master2', 'master3']
```
- name: wait for nodes
  kube:
    command: get
    resource: node
    keyvars: '--output=jsonpath={range .items[*]}{@.metadata.name}:{range @.status.conditions[?(@.type=="Ready")]}{@.type}={@.status};{end}{end}'
    filter: '(\w+\.\w+.\w+):Ready=True;'
  register: k_masters
  changed_when: (k_masters.meta|length) < (masters|length)
  until: not k_masters.changed
  delay: "{{ cluster_wait_delay }}"
  retries: "{{ cluster_wait_retries }}"
```
