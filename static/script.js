document.addEventListener('DOMContentLoaded', function() {
    // Atualiza a data no cabeçalho
    const dateElement = document.getElementById('current-date');
    if (dateElement) {
        const today = new Date();
        dateElement.textContent = today.toLocaleDateString('pt-BR', { year: 'numeric', month: 'long', day: 'numeric' });
    }

    // Gráfico de Movimentações
    const ctx = document.getElementById('movimentacoesChart');
    if (ctx) {
        fetch('/api/chart_data')
            .then(response => response.json())
            .then(data => {
                new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: data.labels,
                        datasets: [{
                            label: 'Entradas',
                            data: data.entradas,
                            borderColor: 'rgba(28, 200, 138, 1)',
                            backgroundColor: 'rgba(28, 200, 138, 0.1)',
                            fill: true,
                            tension: 0.3
                        }, {
                            label: 'Saídas',
                            data: data.saidas,
                            borderColor: 'rgba(231, 74, 59, 1)',
                            backgroundColor: 'rgba(231, 74, 59, 0.1)',
                            fill: true,
                            tension: 0.3
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } }
                });
            })
            .catch(error => console.error('Erro ao buscar dados para o gráfico:', error));
    }

    // Modal de edição de item
    const editItemModal = document.getElementById('editItemModal');
    if (editItemModal) {
        editItemModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;

            const id = button.getAttribute('data-id');
            const nome = button.getAttribute('data-nome');
            const categoria = button.getAttribute('data-categoria');
            const contrato = button.getAttribute('data-contrato');
            const unidade = button.getAttribute('data-unidade');
            const valor = button.getAttribute('data-valor');
            const minimo = button.getAttribute('data-minimo');

            const modalForm = editItemModal.querySelector('form');
            modalForm.action = `/estoque/editar/${id}`;

            editItemModal.querySelector('#edit_nome').value = nome;
            editItemModal.querySelector('#edit_categoria').value = categoria;
            editItemModal.querySelector('#edit_contrato').value = contrato;
            editItemModal.querySelector('#edit_unidade').value = unidade;
            editItemModal.querySelector('#edit_valor_unitario').value = valor;
            editItemModal.querySelector('#edit_estoque_minimo').value = minimo;
        });
    }
});

